"""Testes do caminho Cloudflare Workers: adaptador D1 + runtime bridge.

Usam um fake do binding ``env.DB`` (métodos prepare/bind/all/run) — a mesma
superfície do D1Database do workerd. O FFI real (JsProxy/to_py) não existe no
CPython; cobrimos a conversão com um stub que expõe ``to_py``/atributos.
"""

import asyncio
import logging
import sys
import types
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core import worker_runtime
from app.core.config import settings
from app.db import d1
from app.services import alert_history, persistence

# ---------------------------------------------------------------------------
# Fake do D1Database (memória) — casa exatamente as SQL usadas pelo adapter.
# ---------------------------------------------------------------------------


class FakeStatement:
    """Mimetica D1PreparedStatement: bind(*params) → all()/run()."""

    def __init__(self, database: "FakeD1", sql: str):
        self._database = database
        self._sql = sql
        self._params: tuple = ()

    def bind(self, *params):
        self._params = params
        return self

    async def all(self):
        return self._database.execute(self._sql, self._params)

    async def run(self):
        return self._database.execute(self._sql, self._params)


class FakeD1:
    """Banco em memória com as tabelas do schema (migrations/0001_init.sql)."""

    def __init__(self):
        self.subscribers: dict[str, dict] = {}
        self.alert_logs: list[dict] = []
        self.seen: dict[str, float] = {}
        self.dm_hints: dict[str, float] = {}
        self._next_id = 1

    def prepare(self, sql: str) -> FakeStatement:
        return FakeStatement(self, sql)

    def execute(self, sql: str, params: tuple) -> dict:  # pylint: disable=too-many-branches,too-many-statements
        sql = " ".join(sql.split())
        rows, changes = [], 0

        if sql == "SELECT * FROM subscribers WHERE phone = ?":
            subscriber = self.subscribers.get(params[0])
            rows = [dict(subscriber)] if subscriber else []

        elif sql == "INSERT INTO subscribers (phone, name, is_active) VALUES (?, ?, 1)":
            self.subscribers[params[0]] = {
                "id": self._next_id,
                "phone": params[0],
                "name": params[1],
                "city": None,
                "latitude": None,
                "longitude": None,
                "is_active": 1,
            }
            self._next_id += 1
            changes = 1

        elif sql == (
            "INSERT INTO subscribers (phone, city, latitude, longitude, is_active)"
            " VALUES (?, ?, ?, ?, 0)"
        ):
            self.subscribers[params[0]] = {
                "id": self._next_id,
                "phone": params[0],
                "name": None,
                "city": params[1],
                "latitude": params[2],
                "longitude": params[3],
                "is_active": 0,
            }
            self._next_id += 1
            changes = 1

        elif sql.startswith("UPDATE subscribers SET is_active = 1"):
            subscriber = self.subscribers[params[-1]]
            subscriber["is_active"] = 1
            if "name = ?" in sql:
                subscriber["name"] = params[0]
            changes = 1

        elif sql == "UPDATE subscribers SET is_active = 0 WHERE phone = ?":
            self.subscribers[params[0]]["is_active"] = 0
            changes = 1

        elif sql == (
            "UPDATE subscribers SET city = ?, latitude = ?, longitude = ?"
            " WHERE phone = ?"
        ):
            subscriber = self.subscribers[params[3]]
            subscriber["city"] = params[0]
            subscriber["latitude"] = params[1]
            subscriber["longitude"] = params[2]
            changes = 1

        elif sql == (
            "UPDATE subscribers SET city = NULL, latitude = NULL, longitude = NULL"
            " WHERE phone = ?"
        ):
            subscriber = self.subscribers[params[0]]
            subscriber["city"] = None
            subscriber["latitude"] = None
            subscriber["longitude"] = None
            changes = 1

        elif sql == "SELECT * FROM subscribers WHERE is_active = 1":
            rows = [
                dict(sub) for sub in self.subscribers.values() if sub["is_active"]
            ]

        elif sql.startswith("INSERT INTO alert_logs"):
            self.alert_logs.append(
                {
                    "id": self._next_id,
                    "alert_type": params[0],
                    "recipient": params[1],
                    "delivery_status": params[2],
                    "subscriber_id": params[3],
                }
            )
            self._next_id += 1
            changes = 1

        elif sql.startswith("INSERT OR IGNORE INTO seen_messages"):
            if params[0] in self.seen:
                changes = 0
            else:
                self.seen[params[0]] = params[1]
                changes = 1

        elif sql == "INSERT OR IGNORE INTO dm_hints (phone, shown_at) VALUES (?, ?)":
            if params[0] in self.dm_hints:
                changes = 0
            else:
                self.dm_hints[params[0]] = params[1]
                changes = 1

        elif sql == "DELETE FROM seen_messages WHERE seen_at < ?":
            expired = [k for k, seen_at in self.seen.items() if seen_at < params[0]]
            for key in expired:
                self.seen.pop(key)
            changes = len(expired)

        elif sql == "SELECT 1 AS ok":
            rows = [{"ok": 1}]

        else:
            raise AssertionError(f"SQL não prevista no fake: {sql}")

        return {"results": rows, "meta": {"changes": changes}, "success": True}


@pytest.fixture(name="workers_env")
def fake_workers_env_fixture():
    """Anexa um env de Workers fake (env.DB em memória) e restaura tudo."""
    snapshot = {key: getattr(settings, key) for key in worker_runtime.SYNCED_KEYS}
    env = SimpleNamespace(DB=FakeD1())
    worker_runtime.attach(env)
    yield env
    worker_runtime.reset_for_tests()
    for key, value in snapshot.items():
        setattr(settings, key, value)


# ---------------------------------------------------------------------------
# Runtime bridge
# ---------------------------------------------------------------------------


def test_attach_syncs_uppercase_vars_and_exposes_d1(workers_env):
    assert worker_runtime.on_workers() is True
    assert worker_runtime.d1() is workers_env.DB


def test_attach_noop_without_env():
    worker_runtime.reset_for_tests()
    worker_runtime.attach(None)
    assert worker_runtime.on_workers() is False
    assert worker_runtime.d1() is None


@pytest.mark.parametrize(
    ("iso_utc", "expected_hour"),
    [
        ("2026-01-15T09:00:00", 6),  # 09h UTC → 06h BRT (alerta + boletim)
        ("2026-01-15T11:00:00", 8),  # 08h BRT (alerta)
        ("2026-01-15T23:00:00", 20),  # 20h BRT (boletim da noite)
        ("2026-01-16T02:00:00", 23),  # 23h BRT (vira o dia)
    ],
)
def test_brt_hour(iso_utc, expected_hour):
    moment = datetime.fromisoformat(iso_utc).replace(tzinfo=timezone.utc)
    assert worker_runtime.brt_hour(int(moment.timestamp() * 1000)) == expected_hour


# ---------------------------------------------------------------------------
# Persistência via D1
# ---------------------------------------------------------------------------


def test_subscribe_unsubscribe_flow_via_d1(workers_env):
    async def flow():
        first = await persistence.subscribe_recipient("+5588999999999", " Ana ")
        again = await persistence.subscribe_recipient("+5588999999999")
        canceled = await persistence.unsubscribe_recipient("+5588999999999")
        twice = await persistence.unsubscribe_recipient("+5588999999999")
        reactivated = await persistence.subscribe_recipient(
            "+5588999999999", "Ana Maria"
        )
        return first, again, canceled, twice, reactivated

    first, again, canceled, twice, reactivated = asyncio.run(flow())

    assert first["status"] == "success"
    assert again["status"] == "already_subscribed"
    assert canceled["status"] == "success"
    assert twice["status"] == "not_found"
    assert reactivated["status"] == "success"

    stored = workers_env.DB.subscribers["+5588999999999"]
    assert stored["is_active"] == 1
    assert stored["name"] == "Ana Maria"


def test_location_roundtrip_and_grouping_via_d1(workers_env):  # pylint: disable=unused-argument
    async def flow():
        await persistence.set_subscriber_location(
            "+5588111111111", "Crato", -7.2342, -39.4086
        )
        await persistence.subscribe_recipient("+5588111111111")
        await persistence.subscribe_recipient("+5588222222222")
        location = await persistence.get_subscriber_location("+5588111111111")
        default_location = await persistence.get_subscriber_location("+5588222222222")
        groups = await persistence.group_active_subscribers_by_city()
        return location, default_location, groups

    location, default_location, groups = asyncio.run(flow())

    assert location == {
        "name": "Crato",
        "latitude": -7.2342,
        "longitude": -39.4086,
    }
    assert default_location is None
    assert [subscriber.phone for subscriber in groups["Crato"]] == ["+5588111111111"]
    assert [subscriber.phone for subscriber in groups[""]] == ["+5588222222222"]


def test_location_clear_returns_to_default_via_d1(workers_env):  # pylint: disable=unused-argument
    async def flow():
        await persistence.set_subscriber_location(
            "+5588333344444", "-7.23, -39.31", -7.23, -39.31
        )
        await persistence.clear_subscriber_location("+5588333344444")
        return await persistence.get_subscriber_location("+5588333344444")

    assert asyncio.run(flow()) is None
    stored = workers_env.DB.subscribers["+5588333344444"]
    assert (stored["city"], stored["latitude"], stored["longitude"]) == (None, None, None)


def test_legacy_city_without_coords_resolves_preset_via_d1(workers_env):  # pylint: disable=unused-argument
    workers_env.DB.subscribers["+5588666666666"] = {
        "id": 99,
        "phone": "+5588666666666",
        "name": None,
        "city": "Crato",
        "latitude": None,
        "longitude": None,
        "is_active": 1,
    }

    location = asyncio.run(persistence.get_subscriber_location("+5588666666666"))

    assert location["name"] == "Crato"
    assert location["latitude"] == pytest.approx(-7.2342)


def test_dm_hint_shown_only_once_via_d1(workers_env):  # pylint: disable=unused-argument
    async def flow():
        first = await persistence.should_hint_dm("+5588555555555")
        second = await persistence.should_hint_dm("+5588555555555")
        other = await persistence.should_hint_dm("+5588555500000")
        return first, second, other

    first, second, other = asyncio.run(flow())

    assert first is True
    assert second is False
    assert other is True


def test_alert_history_via_d1(workers_env):
    asyncio.run(
        alert_history.record_alert_dispatch(
            "weather_alert", "+5588333333333", "sent", subscriber_id=7
        )
    )

    log = workers_env.DB.alert_logs[0]
    assert log["alert_type"] == "weather_alert"
    assert log["recipient"] == "+5588333333333"
    assert log["delivery_status"] == "sent"
    assert log["subscriber_id"] == 7


def test_dedupe_first_seen_then_duplicate(workers_env):  # pylint: disable=unused-argument
    async def flow():
        first = await persistence.is_duplicate_message("msg-1")
        second = await persistence.is_duplicate_message("msg-1")
        other = await persistence.is_duplicate_message("msg-2")
        return first, second, other

    first, second, other = asyncio.run(flow())

    assert first is False
    assert second is True
    assert other is False


def test_d1_ping(workers_env):  # pylint: disable=unused-argument
    asyncio.run(d1.ping())  # não deve levantar exceção


# ---------------------------------------------------------------------------
# Trabalho de fundo (ctx.waitUntil) — o webhook responde sem esperar o envio
# ---------------------------------------------------------------------------


def test_defer_no_cpython_devolve_false():
    """No Docker o chamador cai no BackgroundTasks do FastAPI."""
    assert worker_runtime.defer(lambda: asyncio.sleep(0)) is False


def _fake_workers_sdk(monkeypatch, registered):
    sdk = types.ModuleType("workers")
    sdk.wait_until = registered.append
    monkeypatch.setitem(sys.modules, "workers", sdk)
    monkeypatch.setattr(worker_runtime, "is_workers_runtime", lambda: True)


def test_defer_no_workers_registra_wait_until(monkeypatch):
    registered: list = []
    _fake_workers_sdk(monkeypatch, registered)

    async def work():
        return "ok"

    async def flow():
        assert worker_runtime.defer(work) is True
        await registered[0]

    asyncio.run(flow())

    assert registered[0].result() == "ok"


def test_defer_loga_erro_do_trabalho_de_fundo(monkeypatch, caplog):
    registered: list = []
    _fake_workers_sdk(monkeypatch, registered)

    async def boom():
        raise RuntimeError("falhou depois do 200")

    async def flow():
        worker_runtime.defer(boom)
        await asyncio.wait([registered[0]])
        await asyncio.sleep(0)  # deixa o done_callback rodar

    with caplog.at_level(logging.ERROR):
        asyncio.run(flow())

    assert "trabalho de fundo" in caplog.text


def test_health_check_uses_d1_when_attached(  # pylint: disable=unused-argument
    workers_env, test_database
):
    """No Workers o /health valida o banco via binding D1 (não SQLAlchemy)."""
    from app.main import app as main_app  # import local evita ciclo no topo

    client = TestClient(main_app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["services"]["database"] == "healthy"


# ---------------------------------------------------------------------------
# Conversão FFI (stub com to_py/atributos, no lugar do JsProxy real)
# ---------------------------------------------------------------------------


class _JsRow:
    """Stub de JsProxy de linha: só expõe to_py()."""

    def __init__(self, data):
        self._data = data

    def to_py(self):
        return self._data


class _JsMeta:
    def __init__(self, changes):
        self.changes = changes

    def to_py(self):
        return {"changes": self.changes}


class _JsResult:
    """Stub de D1Result com acesso por atributo (estilo JsProxy)."""

    def __init__(self, rows, changes):
        self.results = [_JsRow(row) for row in rows]
        self.meta = _JsMeta(changes)


def test_rows_and_changes_convert_js_style_results():
    result = _JsResult([{"id": 1, "phone": "+5588", "is_active": 1}], changes=1)

    rows = d1._rows(result)  # pylint: disable=protected-access
    changes = d1._changes(result)  # pylint: disable=protected-access

    assert rows == [{"id": 1, "phone": "+5588", "is_active": 1}]
    assert changes == 1

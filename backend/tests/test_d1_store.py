"""Testes do caminho Cloudflare Workers: adaptador D1 + runtime bridge.

Usam um fake do binding ``env.DB`` (métodos prepare/bind/all/run) — a mesma
superfície do D1Database do workerd. O FFI real (JsProxy/to_py) não existe no
CPython; cobrimos a conversão com um stub que expõe ``to_py``/atributos.
"""

import asyncio
import logging
import sys
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core import worker_runtime
from app.core.config import settings
from app.db import d1
from app.services import admin_sessions, alert_history, persistence

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
        self.admin_sessions: dict[str, dict] = {}
        self._next_id = 1

    def prepare(self, sql: str) -> FakeStatement:
        return FakeStatement(self, sql)

    def execute(self, sql: str, params: tuple) -> dict:  # pylint: disable=too-many-branches,too-many-statements
        sql = " ".join(sql.split())
        rows, changes = [], 0

        if sql == "SELECT * FROM subscribers WHERE phone = ?":
            subscriber = self.subscribers.get(params[0])
            rows = [dict(subscriber)] if subscriber else []

        elif sql == "INSERT INTO subscribers (phone, name, is_active, receive_alerts, receive_bulletins, bulletin_time, awaiting_gps, gps_expires_at) VALUES (?, ?, ?, ?, ?, NULL, 0, NULL)":
            self.subscribers[params[0]] = {
                "id": self._next_id,
                "phone": params[0],
                "name": params[1],
                "city": None,
                "latitude": None,
                "longitude": None,
                "is_active": params[2],
                "receive_alerts": params[3],
                "receive_bulletins": params[4],
                "bulletin_time": None,
                "awaiting_gps": 0,
                "gps_expires_at": None,
            }
            self._next_id += 1
            changes = 1

        elif sql == (
            "INSERT INTO subscribers (phone, city, latitude, longitude, is_active, "
            "receive_alerts, receive_bulletins, bulletin_time, awaiting_gps, gps_expires_at) VALUES (?, ?, ?, ?, 0, 0, 0, NULL, 0, NULL)"
        ):
            self.subscribers[params[0]] = {
                "id": self._next_id,
                "phone": params[0],
                "name": None,
                "city": params[1],
                "latitude": params[2],
                "longitude": params[3],
                "is_active": 0,
                "receive_alerts": 0,
                "receive_bulletins": 0,
                "bulletin_time": None,
                "awaiting_gps": 0,
                "gps_expires_at": None,
            }
            self._next_id += 1
            changes = 1

        elif sql.startswith("UPDATE subscribers SET is_active = ?"):
            # new subscribe update: is_active=?, receive_alerts=?, receive_bulletins=?, [name=?], phone=?
            # params order: is_active, receive_alerts, receive_bulletins, (name?), phone
            subscriber = self.subscribers[params[-1]]
            subscriber["is_active"] = params[0]
            subscriber["receive_alerts"] = params[1]
            subscriber["receive_bulletins"] = params[2]
            if "name = ?" in sql:
                subscriber["name"] = params[3]
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

        elif sql == "UPDATE subscribers SET bulletin_time = ? WHERE phone = ?":
            subscriber = self.subscribers.get(params[1])
            if subscriber is not None:
                subscriber["bulletin_time"] = params[0]
                changes = 1

        elif sql == "UPDATE subscribers SET awaiting_gps = ?, gps_expires_at = ? WHERE phone = ?":
            subscriber = self.subscribers.get(params[2])
            if subscriber is not None:
                subscriber["awaiting_gps"] = params[0]
                subscriber["gps_expires_at"] = params[1]
                changes = 1

        elif sql == "UPDATE subscribers SET awaiting_gps = 0, gps_expires_at = NULL WHERE phone = ?":
            subscriber = self.subscribers.get(params[0])
            if subscriber is not None:
                subscriber["awaiting_gps"] = 0
                subscriber["gps_expires_at"] = None
                changes = 1

        elif sql == "INSERT INTO subscribers (phone, is_active, receive_alerts, receive_bulletins, awaiting_gps, gps_expires_at) VALUES (?, 0, 0, 0, ?, ?)":
            self.subscribers[params[0]] = {
                "id": self._next_id,
                "phone": params[0],
                "name": None,
                "city": None,
                "latitude": None,
                "longitude": None,
                "is_active": 0,
                "receive_alerts": 0,
                "receive_bulletins": 0,
                "bulletin_time": None,
                "awaiting_gps": params[1],
                "gps_expires_at": params[2],
            }
            self._next_id += 1
            changes = 1

        elif sql == "INSERT INTO subscribers (phone, is_active, receive_alerts, receive_bulletins, bulletin_time) VALUES (?, 0, 0, 0, ?)":
            self.subscribers[params[0]] = {
                "id": self._next_id,
                "phone": params[0],
                "name": None,
                "city": None,
                "latitude": None,
                "longitude": None,
                "is_active": 0,
                "receive_alerts": 0,
                "receive_bulletins": 0,
                "bulletin_time": params[1],
            }
            self._next_id += 1
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

        elif sql.startswith("SELECT * FROM subscribers WHERE is_active = 1 AND substr(phone, -5)"):
            suffix = params[0] if params else ""
            rows = [
                dict(sub) for sub in self.subscribers.values()
                if sub["is_active"] and str(sub["phone"]).endswith(suffix)
            ]

        elif sql.startswith("INSERT INTO alert_logs"):
            self.alert_logs.append(
                {
                    "id": self._next_id,
                    # default da tabela no D1: datetime('now') em UTC
                    "sent_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    "alert_type": params[0],
                    "recipient": params[1],
                    "delivery_status": params[2],
                    "subscriber_id": params[3],
                }
            )
            self._next_id += 1
            changes = 1

        elif sql.startswith("DELETE FROM alert_logs WHERE sent_at < datetime('now', ?)"):
            dias = int(params[0].split()[0])
            cutoff = (datetime.now(timezone.utc) + timedelta(days=dias)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            mantidos = [log for log in self.alert_logs if log["sent_at"] >= cutoff]
            changes = len(self.alert_logs) - len(mantidos)
            self.alert_logs = mantidos

        elif sql.startswith(
            "SELECT alert_type, recipient, delivery_status, sent_at FROM alert_logs"
        ):
            ordered = sorted(
                self.alert_logs, key=lambda log: log["id"], reverse=True
            )
            rows = [
                {
                    "alert_type": log["alert_type"],
                    "recipient": log["recipient"],
                    "delivery_status": log["delivery_status"],
                    "sent_at": log["sent_at"],
                }
                for log in ordered[: params[0]]
            ]

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

        elif sql.startswith("INSERT INTO admin_sessions"):
            self.admin_sessions[params[0]] = {
                "phone": params[0],
                "password_fingerprint": params[1],
                "registered_at": params[2],
                "expires_at": params[3],
                "notified_at": None,
            }
            changes = 1

        elif (
            "FROM admin_sessions WHERE phone = ?"
            " AND password_fingerprint = ? AND expires_at > ?" in sql
        ):
            session = self.admin_sessions.get(params[0])
            if (
                session
                and session["password_fingerprint"] == params[1]
                and session["expires_at"] > params[2]
            ):
                rows = [dict(session)]

        elif (
            "FROM admin_sessions WHERE expires_at <= ?"
            " AND notified_at IS NULL" in sql
        ):
            expired = [
                dict(session)
                for session in self.admin_sessions.values()
                if session["expires_at"] <= params[0]
                and session["notified_at"] is None
            ]
            expired.sort(key=lambda session: session["expires_at"])
            rows = expired[: params[1]]

        elif sql == "UPDATE admin_sessions SET notified_at = ? WHERE phone = ?":
            session = self.admin_sessions.get(params[1])
            if session is not None:
                session["notified_at"] = params[0]
                changes = 1

        elif sql == "DELETE FROM admin_sessions WHERE phone = ?":
            if self.admin_sessions.pop(params[0], None) is not None:
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


def test_attach_syncs_admin_password_as_secret(monkeypatch):
    from pydantic import SecretStr  # pylint: disable=import-outside-toplevel

    monkeypatch.setattr(settings, "admin_password", SecretStr(""))
    worker_runtime.reset_for_tests()
    env = SimpleNamespace(ADMIN_PASSWORD="senha-sincronizada-123")

    worker_runtime.attach(env)

    assert settings.admin_password.get_secret_value() == "senha-sincronizada-123"
    worker_runtime.reset_for_tests()


def test_attach_noop_without_env():
    worker_runtime.reset_for_tests()
    worker_runtime.attach(None)
    assert worker_runtime.on_workers() is False
    assert worker_runtime.d1() is None


def test_scheduled_env_prefere_argumento_e_cai_no_self_env(workers_env):
    """O runtime antigo chama `scheduled` com env=None (só `self.env` tem o D1)."""
    other = SimpleNamespace(DB=object())
    assert worker_runtime.scheduled_env(SimpleNamespace(env=workers_env), other) is other
    assert worker_runtime.scheduled_env(SimpleNamespace(env=workers_env), None) is workers_env
    assert worker_runtime.scheduled_env(SimpleNamespace(), None) is None


def test_storage_errors_no_workers_nunca_importa_sqlalchemy(monkeypatch):
    """Sem env anexado, o erro não pode virar `No module named 'sqlalchemy'`."""
    from app.db.errors import storage_errors  # pylint: disable=import-outside-toplevel

    monkeypatch.setattr(worker_runtime, "is_workers_runtime", lambda: True)
    worker_runtime.reset_for_tests()
    assert storage_errors() == (RuntimeError,)


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


def test_prune_alert_logs_via_d1(workers_env):
    async def flow():
        await alert_history.record_alert_dispatch("weather_alert", "+5588", "sent")
        await alert_history.record_alert_dispatch("weather_alert", "+5599", "sent")
        # envelhece o primeiro: o prune por retenção deve levar só ele
        workers_env.DB.alert_logs[0]["sent_at"] = "2020-01-01 00:00:00"
        return await alert_history.prune_alert_logs(90)

    assert asyncio.run(flow()) == 1
    assert [log["recipient"] for log in workers_env.DB.alert_logs] == ["+5599"]


def test_recent_alert_dispatches_via_d1(workers_env):  # pylint: disable=unused-argument
    async def flow():
        await alert_history.record_alert_dispatch("forecast_morning", "+5588", "sent")
        await alert_history.record_alert_dispatch("weather_alert", "+5599", "failed")
        return await alert_history.recent_alert_dispatches(1)

    rows = asyncio.run(flow())

    assert len(rows) == 1
    assert rows[0]["alert_type"] == "weather_alert"
    assert rows[0]["recipient"] == "+5599"
    assert rows[0]["delivery_status"] == "failed"


def test_sessao_administrativa_via_d1(workers_env):  # pylint: disable=unused-argument
    phone = "+5588999999999"
    fingerprint = admin_sessions.password_fingerprint("senha-de-teste")

    async def flow():
        expires = await admin_sessions.register_admin_session(
            phone, fingerprint, now=1_000.0
        )
        active = await admin_sessions.get_admin_session(
            phone, fingerprint, now=1_001.0
        )
        wrong_password = await admin_sessions.get_admin_session(
            phone, "outro-fingerprint", now=1_001.0
        )
        expired_at = 1_000.0 + admin_sessions.ADMIN_SESSION_SECONDS + 1
        expired = await admin_sessions.list_expired_admin_sessions(now=expired_at)
        await admin_sessions.mark_admin_session_notified(phone, notified_at=expired_at)
        after_notice = await admin_sessions.list_expired_admin_sessions(now=expired_at)
        revoked = await admin_sessions.revoke_admin_session(phone)
        return expires, active, wrong_password, expired, after_notice, revoked

    expires, active, wrong_password, expired, after_notice, revoked = asyncio.run(
        flow()
    )

    assert expires == 1_000.0 + admin_sessions.ADMIN_SESSION_SECONDS
    assert active["phone"] == phone
    assert wrong_password is None
    assert [session["phone"] for session in expired] == [phone]
    assert after_notice == []
    assert revoked is True
    assert not workers_env.DB.admin_sessions


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

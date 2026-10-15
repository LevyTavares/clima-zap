import asyncio

import pytest
from evolution_api import EvolutionConnectionError
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.main as main_module
from app.services import persistence, weather_dispatch
from app.services.persistence import resolve_group_location
from app.main import app
from app.models import AlertLog, Subscriber


def test_subscription_persists_and_can_be_reactivated(test_database):
    client = TestClient(app)

    subscribed = client.post(
        "/api/v1/subscribe",
        json={"phone": "+15551234567", "name": "Ana", "action": "subscribe"},
    )
    canceled = client.post(
        "/api/v1/subscribe",
        json={"phone": "+15551234567", "action": "unsubscribe"},
    )
    reactivated = client.post(
        "/api/v1/subscribe",
        json={"phone": "+15551234567", "name": "Ana Silva", "action": "subscribe"},
    )

    assert subscribed.json()["status"] == "success"
    assert canceled.json()["status"] == "success"
    assert reactivated.json()["status"] == "success"

    async def read_subscriber():
        async with test_database() as session:
            result = await session.execute(
                select(Subscriber).where(Subscriber.phone == "+15551234567")
            )
            return result.scalar_one()

    subscriber = asyncio.run(read_subscriber())
    assert subscriber.is_active is True
    assert subscriber.name == "Ana Silva"
    assert subscriber.registered_at is not None


def test_successful_forecast_is_added_to_alert_history(test_database, monkeypatch):
    monkeypatch.setattr(main_module.settings, "forecast_group_jid", "forecast-group")

    async def fake_build_forecast(period):
        return f"forecast-{period}"

    async def fake_send_message(recipient, message):
        assert recipient == "forecast-group"
        assert message == "forecast-afternoon"
        return {"status": "sent"}

    monkeypatch.setattr(main_module, "build_period_forecast", fake_build_forecast)
    monkeypatch.setattr(main_module, "send_whatsapp_message", fake_send_message)

    asyncio.run(main_module.send_period_forecast("afternoon"))

    async def read_alert_log():
        async with test_database() as session:
            result = await session.execute(select(AlertLog))
            return result.scalar_one()

    alert_log = asyncio.run(read_alert_log())
    assert alert_log.alert_type == "forecast_afternoon"
    assert alert_log.delivery_status == "sent"
    assert alert_log.recipient == "forecast-group"
    assert alert_log.sent_at is not None


def test_failed_forecast_is_added_to_alert_history(test_database, monkeypatch):
    monkeypatch.setattr(main_module.settings, "forecast_group_jid", "forecast-group")

    async def fake_build_forecast(period):
        return f"forecast-{period}"

    async def failed_send_message(*args):
        assert args == ("forecast-group", "forecast-morning")
        raise EvolutionConnectionError("provider unavailable")

    monkeypatch.setattr(main_module, "build_period_forecast", fake_build_forecast)
    monkeypatch.setattr(main_module, "send_whatsapp_message", failed_send_message)

    asyncio.run(main_module.send_period_forecast("morning"))

    async def read_alert_log():
        async with test_database() as session:
            result = await session.execute(select(AlertLog))
            return result.scalar_one()

    alert_log = asyncio.run(read_alert_log())
    assert alert_log.alert_type == "forecast_morning"
    assert alert_log.delivery_status == "failed"
    assert alert_log.recipient == "forecast-group"


def test_weather_alert_is_sent_to_active_subscriber(test_database, monkeypatch):
    async def create_subscriber():
        async with test_database() as session:
            subscriber = Subscriber(phone="+15559876543", is_active=True)
            session.add(subscriber)
            await session.commit()

    asyncio.run(create_subscriber())

    async def fake_send_message(recipient, message):
        assert recipient == "+15559876543"
        assert message == "Alerta de UV"
        return {"status": "sent"}

    monkeypatch.setattr(weather_dispatch, "send_whatsapp_message", fake_send_message)
    asyncio.run(weather_dispatch.dispatch_weather_alerts(["Alerta de UV"]))

    async def read_alert_log():
        async with test_database() as session:
            result = await session.execute(select(AlertLog))
            return result.scalar_one()

    alert_log = asyncio.run(read_alert_log())
    assert alert_log.alert_type == "weather_alert"
    assert alert_log.delivery_status == "sent"
    assert alert_log.recipient == "+15559876543"


# ---------------------------------------------------------------------------
# Localização (/configuracao), dica única no privado e agrupamento de alertas
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("test_database")
def test_location_roundtrip_and_reset_via_sqlalchemy():
    async def flow():
        await persistence.set_subscriber_location(
            "+15551112222", "Fortaleza, Ceará", -3.73, -38.53
        )
        location = await persistence.get_subscriber_location("+15551112222")
        await persistence.clear_subscriber_location("+15551112222")
        cleared = await persistence.get_subscriber_location("+15551112222")
        return location, cleared

    location, cleared = asyncio.run(flow())

    assert location == {
        "name": "Fortaleza, Ceará",
        "latitude": -3.73,
        "longitude": -38.53,
    }
    assert cleared is None


def test_legacy_city_without_coords_resolves_preset(test_database):
    async def create_legacy():
        async with test_database() as session:
            session.add(Subscriber(phone="+15555556666", city="Crato", is_active=True))
            await session.commit()

    asyncio.run(create_legacy())
    location = asyncio.run(persistence.get_subscriber_location("+15555556666"))

    assert location["name"] == "Crato"
    assert location["latitude"] == pytest.approx(-7.2342)
    assert location["longitude"] == pytest.approx(-39.4086)


def test_dm_hint_local_shows_only_once():
    phone = "+15553334444"  # telefone único entre testes (estado em memória)

    assert asyncio.run(persistence.should_hint_dm(phone)) is True
    assert asyncio.run(persistence.should_hint_dm(phone)) is False


def test_resolve_group_location_prefers_coords_then_preset():
    with_coords = Subscriber(
        phone="+15557778888",
        city="Fortaleza, Ceará",
        latitude=-3.73,
        longitude=-38.53,
    )
    preset_only = Subscriber(phone="+15559990000", city="Crato")

    located = resolve_group_location("Crato", [with_coords, preset_only])
    assert located == {
        "name": "Fortaleza, Ceará",
        "latitude": -3.73,
        "longitude": -38.53,
    }

    preset = resolve_group_location("Crato", [preset_only])
    assert preset["name"] == "Crato"
    assert preset["latitude"] == pytest.approx(-7.2342)

    assert resolve_group_location("", [Subscriber(phone="+15550000000")]) is None
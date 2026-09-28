import asyncio

import pytest
from evolution_api import EvolutionConnectionError
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.db.session as db_session
import app.main as main_module
from app.services import weather_dispatch
from app.db.base import Base
from app.main import app
from app.models import AlertLog, Subscriber


@pytest.fixture(name="test_database")
def database_fixture(monkeypatch, tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = create_async_engine(database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def create_schema():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())
    monkeypatch.setattr(db_session, "SessionLocal", session_factory)
    yield session_factory
    asyncio.run(engine.dispose())


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
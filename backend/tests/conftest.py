# backend/tests/conftest.py
import asyncio
import os
import tempfile

# Hermético: o `.env` da raiz (Docker) aponta para o Postgres e vazaria para os
# testes. Fixa um SQLite temporário ANTES de importar settings/app.
_TESTS_DB_DIR = tempfile.mkdtemp(prefix="clima-zap-tests-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TESTS_DB_DIR}/clima_zap.db"

# pylint: disable=wrong-import-position
import pytest  # noqa: E402
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from unittest.mock import patch

# Os imports abaixo vêm depois do DATABASE_URL: `app.core.config` lê o env no
# import, então o SQLite precisa estar definido antes.
import app.api.api as weather_api
import app.db.session as db_session
from app.db.base import Base

# Importe a instância real do seu app FastAPI
from app.main import app


@pytest.fixture(autouse=True)
def _limpa_cache_de_clima():
    """O cache do Open-Meteo (app.api.api) é estado do processo: isolamos."""
    weather_api.clear_weather_cache()
    yield
    weather_api.clear_weather_cache()

@pytest.fixture
def client():
    """
    Fixture que fornece um TestClient do FastAPI para simular requisições HTTP
    nas rotas da nossa aplicação sem precisar subir o servidor.
    """
    return TestClient(app)


@pytest.fixture(name="test_database")
def database_fixture(monkeypatch, tmp_path):
    """Banco SQLite temporário por teste; SessionLocal apontando para ele."""
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


@pytest.fixture
def mock_open_meteo_response():
    """
    Fixture de mock para simular a resposta da API de clima externa.
    Evita chamadas reais de rede durante a suíte de testes.
    """
    mock_data = {
        "city": "Juazeiro do Norte",
        "temp_max": 35.0,
        "temp_min": 22.0,
        "humidity": 45,
        "uv_index": 9.0,
        "rain_prob": 0
    }

    # Intercepta a função que faz o request (ajuste o caminho de importação conforme necessário)
    with patch("app.api.fetch_weather_data") as mock_fetch:
        mock_fetch.return_value = mock_data
        yield mock_fetch

@pytest.fixture
def mock_whatsapp_sender():
    """
    Fixture base para a Task #02. Já deixa preparado para quando 
    o envio assíncrono do WhatsApp for implementado.
    """
    with patch("app.services.whatsapp.send_message") as mock_send:
        mock_send.return_value = {"status": "success", "message_id": "12345"}
        yield mock_send

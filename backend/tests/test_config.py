"""Testes das travas de configuração (CORS e avisos de produção).

Cobrem o endurecimento pedido na revisão de segurança: CORS sem curinga e
por allowlist (lida a cada request, porque no Workers o env chega por
request), e os avisos ``production_warnings`` para defaults inseguros.
"""

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import parse_cors_origins, settings
from app.main import app

client = TestClient(app)

PREFLIGHT_HEADERS = {"Access-Control-Request-Method": "GET"}


def test_parse_cors_origins_ignora_curinga_espacos_e_vazios():
    assert parse_cors_origins("*, https://a.example , http://b.example,") == [
        "https://a.example",
        "http://b.example",
    ]


def test_parse_cors_origins_vazio_significa_sem_cors():
    assert parse_cors_origins("") == []
    assert parse_cors_origins("   ") == []


def test_cors_nao_libera_origem_por_default(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "")

    response = client.options(
        "/health",
        headers={**PREFLIGHT_HEADERS, "Origin": "https://evil.example"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_cors_respeita_allowlist_e_nao_usa_credenciais(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "https://front.example")

    allowed = client.options(
        "/health",
        headers={**PREFLIGHT_HEADERS, "Origin": "https://front.example"},
    )
    denied = client.options(
        "/health",
        headers={**PREFLIGHT_HEADERS, "Origin": "https://evil.example"},
    )

    assert allowed.headers["access-control-allow-origin"] == "https://front.example"
    assert "access-control-allow-credentials" not in allowed.headers
    assert "access-control-allow-origin" not in denied.headers


def test_production_warnings_silencia_fora_de_producao(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "webhook_auth_token", "")
    monkeypatch.setattr(settings, "evolution_api_key", "changeme")
    monkeypatch.setattr(settings, "evolution_api_url", "http://localhost:8080")
    monkeypatch.setattr(settings, "admin_password", SecretStr("curta"))

    assert not settings.production_warnings()


def test_production_warnings_lista_defaults_inseguros(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "webhook_auth_token", "")
    monkeypatch.setattr(settings, "evolution_api_key", "changeme")
    monkeypatch.setattr(settings, "evolution_api_url", "http://localhost:8080")
    monkeypatch.setattr(settings, "admin_password", SecretStr(""))

    warnings = settings.production_warnings()

    assert len(warnings) == 3
    assert any("WEBHOOK_AUTH_TOKEN" in warning for warning in warnings)
    assert any("EVOLUTION_API_KEY" in warning for warning in warnings)
    assert any("HTTPS" in warning for warning in warnings)


def test_production_warnings_vazio_com_config_segura(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "webhook_auth_token", "s3cret")
    monkeypatch.setattr(settings, "evolution_api_key", "chave-real")
    monkeypatch.setattr(settings, "evolution_api_url", "https://evo.example.com")
    monkeypatch.setattr(
        settings, "admin_password", SecretStr("senha-segura-de-teste-123")
    )

    assert not settings.production_warnings()


def test_production_warnings_admin_password_curta(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "webhook_auth_token", "s3cret")
    monkeypatch.setattr(settings, "evolution_api_key", "chave-real")
    monkeypatch.setattr(settings, "evolution_api_url", "https://evo.example.com")
    monkeypatch.setattr(settings, "admin_password", SecretStr("curta"))

    warnings = settings.production_warnings()

    assert len(warnings) == 1
    assert "ADMIN_PASSWORD" in warnings[0]

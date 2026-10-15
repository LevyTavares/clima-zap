from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py → parents[3] = repo root
ROOT_DIR = Path(__file__).resolve().parents[3]
ROOT_ENV = ROOT_DIR / ".env"


class Settings(BaseSettings):
    # Application basics
    port: int = 8000
    environment: str = "development"
    default_city: str = "Triângulo, Juazeiro do Norte"
    default_latitude: float = -7.229711
    default_longitude: float = -39.3300014
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"
    evolution_api_url: str = "http://localhost:8080"
    evolution_api_key: str = ""
    evolution_instance_name: str = ""
    # Número do próprio bot (só dígitos) — usado para detectar menções nativas
    # do WhatsApp (@número) que apontem para o bot na gramática de comandos.
    target_phone_number: str = ""
    # Nome do bot na invocação textual: "@clima-zap previsao".
    bot_name: str = "clima-zap"
    forecast_group_jid: str = ""
    # Token opcional exigido no header `Authorization: Bearer <token>` do webhook.
    # Vazio = sem verificação. Configure também um header custom no webhook da Evolution.
    webhook_auth_token: str = ""
    docs_dir: str = ""
    database_url: SecretStr = SecretStr("sqlite+aiosqlite:///./clima_zap.db")
    database_ssl: bool = False

    model_config = SettingsConfigDict(
        env_file=ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


def normalized_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url

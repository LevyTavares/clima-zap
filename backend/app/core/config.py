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
    target_phone_number: str = ""
    forecast_group_jid: str = ""
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

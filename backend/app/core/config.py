from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py → parents[3] = repo root
ROOT_DIR = Path(__file__).resolve().parents[3]
ROOT_ENV = ROOT_DIR / ".env"


class Settings(BaseSettings):
    port: int = 8000
    environment: str = "development"
    default_city: str = "Juazeiro do Norte"
    default_latitude: float = -7.2128
    default_longitude: float = -39.3151
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"
    evolution_api_url: str = "http://localhost:8080"
    evolution_api_key: str = ""
    evolution_instance_name: str = ""
    target_phone_number: str = ""
    forecast_group_jid: str = ""
    docs_dir: str = ""

    model_config = SettingsConfigDict(
        env_file=ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

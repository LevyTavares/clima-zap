from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    evolution_api_url: str = ""
    evolution_api_key: str = ""
    evolution_instance_name: str = ""
    target_phone_number: str = ""
    default_city: str = "Juazeiro do Norte"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

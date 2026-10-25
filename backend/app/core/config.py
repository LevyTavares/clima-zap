from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py → parents[3] = repo root
ROOT_DIR = Path(__file__).resolve().parents[3]
ROOT_ENV = ROOT_DIR / ".env"

# Valores default/placeholder que nunca devem valer em produção
# (EVOLUTION_API_KEY, POSTGRES_PASSWORD do Compose).
INSECURE_SECRETS = frozenset(
    {"", "changeme", "evolution_pass", "troque-esta-chave", "troque-esta-senha"}
)


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
    # Comando /admin (só no privado): vazio = administração desabilitada.
    # Use uma senha longa e aleatória (`openssl rand -hex 16`).
    admin_password: SecretStr = SecretStr("")
    # Opcional: número do WhatsApp (só dígitos, com DDI) autorizado a usar
    # /admin. Vazio = qualquer privado que saiba a senha.
    admin_phone: str = ""
    docs_dir: str = ""
    database_url: SecretStr = SecretStr("sqlite+aiosqlite:///./clima_zap.db")
    database_ssl: bool = False
    # Origens liberadas no CORS, separadas por vírgula (ex.:
    # "https://clima-zap.vercel.app"). Vazio = nenhuma origem cross-origin.
    # O curinga `*` é descartado de propósito — veja `parse_cors_origins`.
    cors_origins: str = ""

    model_config = SettingsConfigDict(
        env_file=ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        """True quando ``ENVIRONMENT`` aponta para produção."""
        return self.environment.strip().lower() in ("production", "prod")

    def production_warnings(self) -> list[str]:
        """Configs inseguras que ficaram ativas em produção.

        Fora de produção retorna lista vazia: os defaults de desenvolvimento
        (localhost, chave placeholder) são esperados e não geram ruído.
        """
        if not self.is_production:
            return []
        warnings: list[str] = []
        if not self.webhook_auth_token:
            warnings.append(
                "WEBHOOK_AUTH_TOKEN vazio: o webhook recusa requisições em "
                "produção (`wrangler secret put WEBHOOK_AUTH_TOKEN`)"
            )
        if self.evolution_api_key.strip().lower() in INSECURE_SECRETS:
            warnings.append(
                "EVOLUTION_API_KEY com valor default/placeholder: troque antes "
                "de usar (ex.: `openssl rand -hex 32`)"
            )
        if not self.evolution_api_url.lower().startswith("https://"):
            warnings.append(
                f"EVOLUTION_API_URL sem HTTPS ({self.evolution_api_url}): a API "
                "key trafega nesse host — exponha a Evolution por HTTPS público"
            )
        admin_password = self.admin_password.get_secret_value()
        if admin_password and admin_password.strip().lower() in INSECURE_SECRETS:
            warnings.append(
                "ADMIN_PASSWORD com valor default/placeholder: troque antes de "
                "usar (ex.: `openssl rand -hex 16`)"
            )
        if admin_password and len(admin_password) < 12:
            warnings.append(
                "ADMIN_PASSWORD curta: use pelo menos 12 caracteres "
                "(`openssl rand -hex 16`)"
            )
        return warnings


settings = Settings()


def parse_cors_origins(raw: str) -> list[str]:
    """``CORS_ORIGINS`` (vírgula) → lista de origens; vazio = sem CORS.

    ``*`` é descartado de propósito: o middleware do Starlette resolve a lista
    no import, e um curinga silencioso esconderia configuração errada em
    produção — liste as origens explicitamente.
    """
    return [
        origin.strip()
        for origin in raw.split(",")
        if origin.strip() and origin.strip() != "*"
    ]


def normalized_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url

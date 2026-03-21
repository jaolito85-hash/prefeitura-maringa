"""
config.py - Configuracoes centrais da aplicacao.
Prioriza o arquivo .env do projeto antes de variaveis globais do sistema.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_service_key: str

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Evolution API (WhatsApp)
    evolution_api_url: str = ""
    evolution_api_key: str = ""
    wa_instance_name: str = "maringa-demo"          # Instancia unica pra demo
    wa_instance_denuncias: str = "maringa-denuncias"
    wa_instance_sos: str = "maringa-sos-mulher"
    wa_instance_ocorrencias: str = "maringa-ocorrencias"

    # Anthropic (Claude API) — classificador inteligente
    # Pegue em: https://console.anthropic.com → API Keys
    anthropic_api_key: str = ""

    # Seguranca
    webhook_secret: str = ""
    aes_key: str = ""

    # App
    environment: str = "development"
    debug: bool = True
    port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # Evita que variaveis globais do host, como DEBUG, sobrescrevam o .env local.
        return init_settings, dotenv_settings, env_settings, file_secret_settings


settings = Settings()

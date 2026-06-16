"""Configuración central de Tyrion."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Base de datos
    database_url: str = "postgresql+asyncpg://tyrion:tyrion@localhost:5432/tyrion"

    # Anthropic API (clasificación documental con Claude)
    anthropic_api_key: str = ""
    clasificador_model: str = "claude-haiku-4-5-20251001"
    razonador_model: str = "claude-opus-4-8"

    # OpenAI API (clasificador alternativo con visión gpt-4o-mini)
    openai_api_key: str = ""
    clasificador_openai_model: str = "gpt-4o-mini"

    # Umbrales de confianza
    confianza_alta: float = 0.85
    confianza_media: float = 0.60

    # Almacenamiento de documentos
    uploads_dir: str = "/tmp/tyrion_uploads"

    # Watcher de planillas Tempus (CSV drop)
    watch_dir: str = "/tmp/tyrion_watch"

    # Ingesta de email (IMAP). En pruebas: Gmail con app password.
    # En producción: buzón corporativo. Todo por entorno, nada hardcodeado.
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""           # Gmail: app password, NO la contraseña real
    imap_mailbox: str = "INBOX"

    # Envío de avisos salientes (SMTP)
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_remitente: str = ""          # From de los avisos (por defecto = smtp_user)

    # Pantalla Control: usar datos de prueba si no hay BD real
    use_datos_prueba: bool = True

    # Escalado automático: gestoría primero, administrativo como último recurso.
    # T+0 aviso_1 (al detectar el faltante) → T+aviso2 aviso_2 → T+escalado admin.
    escalado_aviso2_min: int = 30
    escalado_admin_min: int = 60
    email_administrativo: str = ""    # destinatario del escalado (último recurso)


@lru_cache
def get_settings() -> Settings:
    return Settings()

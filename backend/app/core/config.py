"""Configuración central de Tyrion."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Base de datos
    database_url: str = "postgresql+asyncpg://tyrion:tyrion@localhost:5432/tyrion"

    # Claude API (clasificación documental)
    anthropic_api_key: str = ""
    # Modelo económico para clasificación masiva; el premium solo en conflictos/escalados
    clasificador_model: str = "claude-haiku-4-5-20251001"
    razonador_model: str = "claude-opus-4-8"

    # Umbrales de confianza
    confianza_alta: float = 0.85
    confianza_media: float = 0.60

    # Almacenamiento de documentos
    uploads_dir: str = "/var/tyrion/uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()

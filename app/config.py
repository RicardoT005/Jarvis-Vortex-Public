"""Configuración central de Jarvis."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Groq
    groq_api_keys: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Base de datos
    database_url: str = "sqlite+aiosqlite:///./data/jarvis.db"

    # Seguridad
    secret_key: str = "cambia-esto-en-produccion"
    admin_username: str = "ricardo"
    admin_password: str = "cambia-esto"

    # Firebase
    firebase_project_id: str = "jarvis-vortex-78100"

    # Entorno
    environment: str = "development"
    debug: bool = True

    # Identidad de Jarvis (no se sobreescribe fácilmente)
    jarvis_name: str = "Jarvis"
    owner_full_name: str = "Ricardo Torres"
    owner_short_name: str = "Ricardo"
    brand_name: str = "MultSoftCreations"
    version: str = "2.0.0"

    @property
    def groq_keys_list(self) -> List[str]:
        if not self.groq_api_keys:
            return []
        return [k.strip() for k in self.groq_api_keys.split(",") if k.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

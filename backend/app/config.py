from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalizar_url(url: str) -> str:
    """Las cadenas de Supabase vienen como postgresql://; SQLAlchemy necesita el driver."""
    for prefijo in ("postgresql://", "postgres://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg://" + url[len(prefijo):]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://guardia:guardia@localhost:5433/guardia"
    test_database_url: str = "postgresql+psycopg://guardia:guardia@localhost:5433/guardia_test"
    app_timezone: str = "America/Argentina/Buenos_Aires"
    modo_demo: bool = False
    # D06: verificación de tokens de Supabase Auth. Con SUPABASE_URL se usan las claves públicas (JWKS) del
    # proyecto; con SUPABASE_JWT_SECRET, el secreto HS256 de los proyectos anteriores. Puede haber ambos.
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    # D30: código de coordinación del servicio. Vacío = nadie puede registrarse como coordinador.
    codigo_coordinacion: str = ""

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _con_driver(cls, valor: str) -> str:
        return _normalizar_url(valor)

    @property
    def zona(self) -> ZoneInfo:
        return ZoneInfo(self.app_timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()

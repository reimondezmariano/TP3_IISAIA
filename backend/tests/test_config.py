from app.config import Settings


def test_normaliza_url_postgresql_al_driver_psycopg():
    s = Settings(database_url="postgresql://u:p@host:5432/db", _env_file=None)
    assert s.database_url == "postgresql+psycopg://u:p@host:5432/db"


def test_normaliza_url_postgres_corta():
    s = Settings(test_database_url="postgres://u:p@localhost:5433/t", _env_file=None)
    assert s.test_database_url == "postgresql+psycopg://u:p@localhost:5433/t"


def test_respeta_url_que_ya_tiene_driver():
    s = Settings(database_url="postgresql+psycopg://u:p@h/db", _env_file=None)
    assert s.database_url == "postgresql+psycopg://u:p@h/db"


def test_zona_por_defecto_es_buenos_aires():
    s = Settings(_env_file=None)
    assert s.zona.key == "America/Argentina/Buenos_Aires"

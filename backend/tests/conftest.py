from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.auth import VerificadorToken, get_verificador
from app.config import get_settings
from app.db import get_db
from app.main import app
from app.modelos import RolUsuario
from app.reloj import RelojFijo, get_reloj
from fabricas import SECRETO_PRUEBA, crear_usuario, encabezados

BACKEND = Path(__file__).resolve().parents[1]
ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
HOSTS_LOCALES = {"localhost", "127.0.0.1", "postgres"}


def verificar_base_local(url: str) -> None:
    """La infraestructura de pruebas borra y recrea la base: nunca contra una base remota."""
    destino = make_url(url)
    if destino.host not in HOSTS_LOCALES:
        raise RuntimeError(
            f"TEST_DATABASE_URL apunta a '{destino.host}'. Las pruebas solo corren contra el Postgres local de docker-compose."
        )
    if not (destino.database or "").endswith("_test"):
        raise RuntimeError(
            f"TEST_DATABASE_URL apunta a la base '{destino.database}'. El nombre debe terminar en '_test': "
            "las pruebas borran y recrean la base."
        )


def _recrear_base(url: str) -> None:
    destino = make_url(url)
    admin = create_engine(destino.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conexion:
        conexion.execute(text(f'DROP DATABASE IF EXISTS "{destino.database}" WITH (FORCE)'))
        conexion.execute(text(f'CREATE DATABASE "{destino.database}"'))
    admin.dispose()


def _vaciar_tablas(engine: Engine) -> None:
    with engine.begin() as conexion:
        tablas = conexion.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'")
        ).scalars().all()
        if tablas:
            lista = ", ".join(f'"{t}"' for t in tablas)
            conexion.execute(text(f"TRUNCATE {lista} RESTART IDENTITY CASCADE"))


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = get_settings().test_database_url
    verificar_base_local(url)
    _recrear_base(url)
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    motor = create_engine(url)
    yield motor
    motor.dispose()


@pytest.fixture
def sesion(engine: Engine) -> Iterator[Session]:
    """Sesión dentro de una transacción que se deshace al terminar la prueba."""
    conexion = engine.connect()
    transaccion = conexion.begin()
    s = Session(bind=conexion, join_transaction_mode="create_savepoint", expire_on_commit=False)
    yield s
    s.close()
    transaccion.rollback()
    conexion.close()


@pytest.fixture
def fabrica_sesiones(engine: Engine, request: pytest.FixtureRequest) -> Iterator[sessionmaker[Session]]:
    """Sesiones que confirman de verdad. Solo para pruebas @pytest.mark.commit_real (concurrencia, F3)."""
    if request.node.get_closest_marker("commit_real") is None:
        raise RuntimeError("fabrica_sesiones solo se usa en pruebas marcadas con @pytest.mark.commit_real")
    yield sessionmaker(bind=engine, expire_on_commit=False)
    _vaciar_tablas(engine)


@pytest.fixture
def cliente(request: pytest.FixtureRequest) -> Iterator[TestClient]:
    if request.node.get_closest_marker("commit_real") is not None:
        fabrica = request.getfixturevalue("fabrica_sesiones")

        def _get_db() -> Iterator[Session]:
            with fabrica() as s:
                yield s
    else:
        compartida = request.getfixturevalue("sesion")

        def _get_db() -> Iterator[Session]:
            yield compartida

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_verificador] = lambda: VerificadorToken(secreto=SECRETO_PRUEBA)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_verificador, None)


@pytest.fixture
def reloj() -> Iterator[RelojFijo]:
    fijo = RelojFijo(datetime(2026, 10, 12, 9, 0, tzinfo=ZONA))
    app.dependency_overrides[get_reloj] = lambda: fijo
    yield fijo
    app.dependency_overrides.pop(get_reloj, None)


@pytest.fixture
def como_coordinador(cliente, sesion, reloj):
    """Enzo, coordinador activo, con su token en el cliente y el reloj fijo en el lunes 12/10/2026."""
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    cliente.headers.update(encabezados(enzo))
    return enzo

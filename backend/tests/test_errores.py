from datetime import date, time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from psycopg import errors
from sqlalchemy.exc import IntegrityError, OperationalError

from app.errores import ErrorDominio
from app.main import crear_app
from app.modelos import VersionHorario
from fabricas import crear_horario_de_prueba, guardar


# Sin frontend/dist: si existe, se monta en "/" y tapa las rutas de prueba agregadas después.
SIN_FRONTEND = Path("no-existe")


def _cliente_con_ruta_de_prueba() -> TestClient:
    app = crear_app(SIN_FRONTEND)

    @app.get("/api/prueba/error")
    def _falla():
        raise ErrorDominio("ALGO_INVALIDO", "Algo no se puede", 409)

    @app.get("/api/prueba/numero")
    def _numero(n: int):
        return {"n": n}

    return TestClient(app)


def test_error_dominio_tiene_status_422_por_defecto():
    assert ErrorDominio("X", "y").status == 422


def test_error_dominio_se_responde_con_formato_unico():
    r = _cliente_con_ruta_de_prueba().get("/api/prueba/error")
    assert r.status_code == 409
    assert r.json() == {"codigo": "ALGO_INVALIDO", "mensaje": "Algo no se puede"}


def test_error_de_validacion_se_reescribe_al_formato_unico():
    r = _cliente_con_ruta_de_prueba().get("/api/prueba/numero", params={"n": "abc"})
    assert r.status_code == 422
    cuerpo = r.json()
    assert set(cuerpo) == {"codigo", "mensaje"}
    assert cuerpo["codigo"] == "VALIDACION"
    assert "n" in cuerpo["mensaje"]


def test_ruta_inexistente_responde_404_con_formato_unico():
    r = _cliente_con_ruta_de_prueba().get("/api/no-existe")
    assert r.status_code == 404
    assert r.json()["codigo"] == "NO_ENCONTRADO"


def _cliente_que_lanza(error: Exception) -> TestClient:
    app = crear_app(SIN_FRONTEND)

    @app.get("/api/prueba/base")
    def _falla_la_base():
        raise error

    return TestClient(app, raise_server_exceptions=False)


def _choque_real_de_versiones(sesion) -> IntegrityError:
    """IntegrityError tal como lo da Postgres al violar ex_version_horario_vigencia (D10)."""
    horario = crear_horario_de_prueba(sesion, None)
    superpuesta = VersionHorario(
        horario_id=horario.id, medico_id=None, dia_semana=2, hora_inicio=time(8), duracion_horas=12,
        frecuencia_semanas=1, fecha_ancla=date(2026, 9, 7), vigente_desde=date(2026, 10, 1),
    )
    with pytest.raises(IntegrityError) as excinfo:
        with sesion.begin_nested():
            guardar(sesion, superpuesta)
    return excinfo.value


def test_choque_de_versiones_responde_409_con_formato_unico(sesion):
    r = _cliente_que_lanza(_choque_real_de_versiones(sesion)).get("/api/prueba/base")
    assert r.status_code == 409
    assert r.json()["codigo"] == "CONFLICTO_DE_VERSION"


def test_deadlock_responde_409_con_formato_unico():
    deadlock = OperationalError("UPDATE usuario ...", {}, errors.DeadlockDetected("deadlock detected"))
    r = _cliente_que_lanza(deadlock).get("/api/prueba/base")
    assert r.status_code == 409
    assert r.json()["codigo"] == "CONFLICTO_CONCURRENTE"


def test_otro_error_de_la_base_sigue_siendo_500():
    caida = OperationalError("SELECT 1", {}, errors.AdminShutdown("the database system is shutting down"))
    assert _cliente_que_lanza(caida).get("/api/prueba/base").status_code == 500

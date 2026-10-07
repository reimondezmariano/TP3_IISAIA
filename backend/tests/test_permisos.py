import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.manejadores import registrar_manejadores
from app.auth import VerificadorToken, get_verificador, requiere_coordinador
from app.db import get_db
from app.modelos import EstadoUsuario, RolUsuario, Usuario
from fabricas import SECRETO_PRUEBA, crear_usuario, encabezados


@pytest.fixture
def cliente_permisos(sesion) -> TestClient:
    app = FastAPI()
    registrar_manejadores(app)

    @app.post("/solo-coordinador")
    def accion(usuario: Usuario = Depends(requiere_coordinador)) -> dict[str, int]:
        return {"id": usuario.id}

    app.dependency_overrides[get_db] = lambda: sesion
    app.dependency_overrides[get_verificador] = lambda: VerificadorToken(secreto=SECRETO_PRUEBA)
    return TestClient(app)


def test_coordinador_activo_puede(cliente_permisos, sesion):
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    r = cliente_permisos.post("/solo-coordinador", headers=encabezados(enzo))
    assert r.status_code == 200
    assert r.json() == {"id": enzo.id}


def test_medico_activo_no_tiene_permiso(cliente_permisos, sesion):
    medico = crear_usuario(sesion, "Carlos Lugones")
    r = cliente_permisos.post("/solo-coordinador", headers=encabezados(medico))
    assert r.status_code == 403
    assert r.json()["codigo"] == "SIN_PERMISO"


def test_coordinador_dado_de_baja_no_pasa_por_su_rol(cliente_permisos, sesion):
    exco = crear_usuario(sesion, "Ex coordinador", rol=RolUsuario.COORDINADOR, estado=EstadoUsuario.BAJA)
    r = cliente_permisos.post("/solo-coordinador", headers=encabezados(exco))
    assert r.status_code == 403
    assert r.json()["codigo"] == "CUENTA_DADA_DE_BAJA"

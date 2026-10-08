import pytest

from app.modelos import EstadoUsuario
from fabricas import crear_usuario, encabezados


def test_activar_un_medico_pendiente(cliente, sesion, como_coordinador):
    nuevo = crear_usuario(sesion, "Médico nuevo", estado=EstadoUsuario.PENDIENTE)

    r = cliente.patch(f"/api/usuarios/{nuevo.id}", json={"estado": "ACTIVO"})

    assert r.status_code == 200
    assert r.json()["usuario"]["estado"] == "ACTIVO"
    assert r.json()["horariosSinTitular"] == []
    assert r.json()["turnosAfectados"] == []
    entra = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-12"}, headers=encabezados(nuevo))
    assert entra.status_code == 200


def test_activar_a_alguien_ya_activo(cliente, sesion, como_coordinador):
    activo = crear_usuario(sesion, "Carlos Lugones")
    r = cliente.patch(f"/api/usuarios/{activo.id}", json={"estado": "ACTIVO"})
    assert (r.status_code, r.json()["codigo"]) == (409, "YA_ACTIVO")


def test_activar_una_baja(cliente, sesion, como_coordinador):
    baja = crear_usuario(sesion, "Se fue", estado=EstadoUsuario.BAJA)
    r = cliente.patch(f"/api/usuarios/{baja.id}", json={"estado": "ACTIVO"})
    assert (r.status_code, r.json()["codigo"]) == (409, "USUARIO_DADO_DE_BAJA")


def test_activar_un_usuario_inexistente(cliente, como_coordinador):
    r = cliente.patch("/api/usuarios/999999", json={"estado": "ACTIVO"})
    assert (r.status_code, r.json()["codigo"]) == (404, "USUARIO_NO_ENCONTRADO")


@pytest.mark.parametrize("estado", ["BAJA", "PENDIENTE"])
def test_patch_solo_pasa_a_activo(cliente, sesion, como_coordinador, estado):
    activo = crear_usuario(sesion, "Carlos Lugones")
    r = cliente.patch(f"/api/usuarios/{activo.id}", json={"estado": estado})
    assert (r.status_code, r.json()["codigo"]) == (422, "VALIDACION")


def test_patch_sin_cambios(cliente, sesion, como_coordinador):
    activo = crear_usuario(sesion, "Carlos Lugones")
    r = cliente.patch(f"/api/usuarios/{activo.id}", json={})
    assert (r.status_code, r.json()["codigo"]) == (422, "SIN_CAMBIOS")


def test_un_medico_no_activa_cuentas(cliente, sesion, reloj):
    medico = crear_usuario(sesion, "Carlos Lugones")
    nuevo = crear_usuario(sesion, "Médico nuevo", estado=EstadoUsuario.PENDIENTE)
    r = cliente.patch(f"/api/usuarios/{nuevo.id}", json={"estado": "ACTIVO"}, headers=encabezados(medico))
    assert (r.status_code, r.json()["codigo"]) == (403, "SIN_PERMISO")

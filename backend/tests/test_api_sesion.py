import uuid
from datetime import date

import pytest

from app.modelos import EstadoUsuario, RolUsuario
from fabricas import crear_usuario, encabezados, token_para


def test_me_devuelve_el_usuario_de_la_sesion(cliente, sesion):
    florencia = crear_usuario(sesion, "Florencia Lucca", email="florencia@prueba.test")

    r = cliente.get("/api/me", headers=encabezados(florencia))

    assert r.status_code == 200
    assert r.json() == {
        "id": florencia.id,
        "nombre": "Florencia Lucca",
        "email": "florencia@prueba.test",
        "rol": "MEDICO",
        "estado": "ACTIVO",
    }


@pytest.mark.parametrize("estado", [EstadoUsuario.PENDIENTE, EstadoUsuario.BAJA])
def test_me_responde_tambien_a_cuentas_sin_acceso(cliente, sesion, estado):
    usuario = crear_usuario(sesion, "Ana Pérez", estado=estado)

    r = cliente.get("/api/me", headers=encabezados(usuario))

    assert r.status_code == 200
    assert r.json()["estado"] == estado.value


def test_me_sin_token_es_401(cliente):
    r = cliente.get("/api/me")
    assert r.status_code == 401
    assert r.json()["codigo"] == "SIN_SESION"


def test_me_de_una_cuenta_sin_registro_es_403(cliente):
    r = cliente.get("/api/me", headers={"Authorization": f"Bearer {token_para(uuid.uuid4())}"})
    assert r.status_code == 403
    assert r.json()["codigo"] == "USUARIO_NO_REGISTRADO"


def test_turnos_sin_token_es_401(cliente):
    r = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-18"})
    assert r.status_code == 401
    assert r.json()["codigo"] == "SIN_SESION"


@pytest.mark.parametrize(
    "estado,codigo",
    [(EstadoUsuario.PENDIENTE, "CUENTA_PENDIENTE"), (EstadoUsuario.BAJA, "CUENTA_DADA_DE_BAJA")],
)
def test_turnos_rechaza_cuentas_sin_acceso(cliente, sesion, estado, codigo):
    usuario = crear_usuario(sesion, "Ana Pérez", estado=estado)

    r = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-18"}, headers=encabezados(usuario))

    assert r.status_code == 403
    assert r.json()["codigo"] == codigo


@pytest.mark.parametrize("rol", [RolUsuario.MEDICO, RolUsuario.COORDINADOR])
def test_turnos_acepta_cualquier_rol_activo(cliente, sesion, rol):
    usuario = crear_usuario(sesion, "Activo", rol=rol)

    r = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-18"}, headers=encabezados(usuario))

    assert r.status_code == 200


def test_baja_programada_sigue_entrando_hasta_su_fecha_inclusive(cliente, sesion, reloj):
    # reloj: lunes 12/10/2026 09:00. D24: activo hasta la fecha de baja inclusive.
    medico = crear_usuario(sesion, "Se va hoy", estado=EstadoUsuario.BAJA, fecha_baja=date(2026, 10, 12))
    r = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-12"}, headers=encabezados(medico))
    assert r.status_code == 200


def test_baja_cumplida_ya_no_entra(cliente, sesion, reloj):
    medico = crear_usuario(sesion, "Se fue ayer", estado=EstadoUsuario.BAJA, fecha_baja=date(2026, 10, 11))
    r = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-12"}, headers=encabezados(medico))
    assert r.status_code == 403
    assert r.json()["codigo"] == "CUENTA_DADA_DE_BAJA"

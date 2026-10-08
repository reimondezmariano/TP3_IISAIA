from sqlalchemy import func, select

from app.modelos import Turno
from fabricas import crear_horario_de_prueba, crear_usuario, encabezados


def consolidados(sesion):
    return sesion.scalar(select(func.count()).select_from(Turno).where(Turno.consolidado_en.is_not(None)))


def test_get_turnos_consolida_antes_de_responder(cliente, sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    cliente.headers.update(encabezados(ana))
    horario = crear_horario_de_prueba(sesion, ana.id)

    r = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-18"})

    assert r.status_code == 200
    assert [t["id"] for t in r.json()] == [f"{horario.id}:2026-10-13"]
    assert consolidados(sesion) == 5


def test_post_consolidacion_devuelve_lo_que_hizo_y_es_idempotente(cliente, sesion, como_coordinador):
    crear_horario_de_prueba(sesion, crear_usuario(sesion, "Ana").id)

    r = cliente.post("/api/consolidacion")
    assert r.status_code == 200
    assert r.json() == {"consolidados": 5, "vacantesSinCobertura": 0, "alertas": 0}

    assert cliente.post("/api/consolidacion").json() == {"consolidados": 0, "vacantesSinCobertura": 0, "alertas": 0}


def test_un_medico_no_fuerza_la_consolidacion(cliente, sesion, reloj):
    cliente.headers.update(encabezados(crear_usuario(sesion, "Ana")))
    r = cliente.post("/api/consolidacion")
    assert r.status_code == 403
    assert r.json()["codigo"] == "SIN_PERMISO"

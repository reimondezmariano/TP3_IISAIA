"""Un cambio de plantilla desde hoy no reescribe el turno de hoy que ya empezó (D11, D12, D20).

El turno de hoy que no tiene fila se calcula desde la plantilla: si el cambio lo alcanzara después de empezar,
la consolidación lo guardaría con otro titular, lo perdería o inventaría uno que no ocurrió.
"""

from datetime import time

from sqlalchemy import select

from app.modelos import Turno
from app.servicios.consolidacion import consolidar_pendientes
from fabricas import HOY, ZONA, crear_horario_de_prueba, crear_usuario


def lunes_de_madrugada(sesion, medico_id):
    return crear_horario_de_prueba(sesion, medico_id, dia=1, hora=time(0), dur=8)  # lunes 00:00 a 08:00


def test_no_cambia_el_titular_desde_hoy_si_el_turno_de_hoy_empezo(cliente, sesion, como_coordinador, reloj):
    ana = crear_usuario(sesion, "Ana")
    beto = crear_usuario(sesion, "Beto")
    h = lunes_de_madrugada(sesion, ana.id)

    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": HOY.isoformat(), "medicoId": beto.id})

    assert r.status_code == 422
    assert r.json()["codigo"] == "TURNO_DE_HOY_EMPEZADO"
    consolidar_pendientes(sesion, reloj, ZONA)
    turno = sesion.scalars(select(Turno).where(Turno.horario_id == h.id, Turno.fecha == HOY)).one()
    assert turno.realizador_id == ana.id


def test_no_cierra_desde_hoy_si_el_turno_de_hoy_empezo(cliente, sesion, como_coordinador):
    h = lunes_de_madrugada(sesion, crear_usuario(sesion, "Ana").id)
    r = cliente.post(f"/api/horarios/{h.id}/cierre", json={"desde": HOY.isoformat()})
    assert r.status_code == 422
    assert r.json()["codigo"] == "TURNO_DE_HOY_EMPEZADO"


def test_no_crea_desde_hoy_un_horario_cuyo_turno_de_hoy_ya_empezo(cliente, sesion, como_coordinador):
    ana = crear_usuario(sesion, "Ana")
    r = cliente.post(
        "/api/horarios",
        json={"medicoId": ana.id, "diaSemana": 1, "horaInicio": "08:00", "duracionHoras": 12, "vigenteDesde": HOY.isoformat()},
    )
    assert r.status_code == 422
    assert r.json()["codigo"] == "TURNO_DE_HOY_EMPEZADO"


def test_no_adelanta_desde_hoy_un_turno_de_hoy_a_un_horario_que_ya_paso(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Ana").id, dia=1, hora=time(20))  # lunes 20:00
    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": HOY.isoformat(), "horaInicio": "06:00"})
    assert r.status_code == 422
    assert r.json()["codigo"] == "TURNO_DE_HOY_EMPEZADO"


def test_desde_hoy_se_permite_si_el_turno_de_hoy_no_empezo(cliente, sesion, como_coordinador):
    ana = crear_usuario(sesion, "Ana")
    beto = crear_usuario(sesion, "Beto")
    cambia, cierra = (crear_horario_de_prueba(sesion, ana.id, dia=1, hora=time(20)) for _ in range(2))  # lunes 20:00
    r = cliente.post(f"/api/horarios/{cambia.id}/versiones", json={"desde": HOY.isoformat(), "medicoId": beto.id})
    assert r.status_code == 201
    r = cliente.post(f"/api/horarios/{cierra.id}/cierre", json={"desde": HOY.isoformat()})
    assert r.status_code == 200

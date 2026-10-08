from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.modelos import EstadoVacante, EventoTurno, TipoEventoTurno, Turno
from app.servicios.consolidacion import consolidar_pendientes
from fabricas import abrir_vacante, crear_horario_de_prueba, crear_usuario, encabezados, guardar_turno

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


@pytest.fixture
def turno_con_vacante(sesion, como_coordinador, reloj):
    ana = crear_usuario(sesion, "Ana")
    turno = guardar_turno(sesion, crear_horario_de_prueba(sesion, ana.id).id, date(2026, 10, 13))
    vacante = abrir_vacante(sesion, turno, ana.id, datetime(2026, 10, 9, tzinfo=ZONA))
    reloj.avanzar(timedelta(days=1, minutes=30))  # martes 13/10 09:30: el turno empezó
    return turno, vacante


def ruta(turno):
    return f"/api/turnos/{turno.horario_id}:{turno.fecha.isoformat()}/sin-cobertura"


def test_el_coordinador_marca_el_turno_sin_cobertura(cliente, sesion, como_coordinador, reloj, turno_con_vacante):
    turno, vacante = turno_con_vacante

    r = cliente.post(ruta(turno))

    assert r.status_code == 200
    assert r.json() == {
        "turnoId": f"{turno.horario_id}:2026-10-13",
        "sinCoberturaEn": "2026-10-13T09:30:00-03:00",
        "vacanteId": vacante.id,
    }
    assert vacante.estado == EstadoVacante.SIN_COBERTURA
    assert vacante.cerrada_en == reloj.ahora()
    assert turno.sin_cobertura_en == reloj.ahora()
    evento = sesion.scalars(select(EventoTurno).where(EventoTurno.turno_id == turno.id)).one()
    assert evento.tipo == TipoEventoTurno.TURNO_SIN_COBERTURA
    assert evento.actor_id == como_coordinador.id
    assert evento.datos == {"vacante_id": vacante.id}


def test_al_consolidar_queda_sin_realizador(cliente, sesion, reloj, turno_con_vacante):
    turno, vacante = turno_con_vacante
    cliente.post(ruta(turno))
    reloj.avanzar(timedelta(hours=11))
    consolidar_pendientes(sesion, reloj, ZONA)
    assert turno.consolidado_en is not None
    assert turno.realizador_id is None
    # La consolidación no vuelve a cerrar la vacante: queda solo el evento del coordinador.
    eventos = sesion.scalars(select(EventoTurno).where(EventoTurno.turno_id == turno.id)).all()
    assert [e.datos for e in eventos] == [{"vacante_id": vacante.id}]


def test_antes_del_inicio_responde_422(cliente, reloj, turno_con_vacante):
    turno, _ = turno_con_vacante
    reloj.avanzar(timedelta(hours=-2))
    r = cliente.post(ruta(turno))
    assert r.status_code == 422
    assert r.json()["codigo"] == "TURNO_NO_EMPEZO"


def test_dos_veces_responde_409(cliente, turno_con_vacante):
    turno, _ = turno_con_vacante
    cliente.post(ruta(turno))
    r = cliente.post(ruta(turno))
    assert r.status_code == 409
    assert r.json()["codigo"] == "YA_SIN_COBERTURA"


def test_turno_consolidado_responde_409(cliente, sesion, reloj, turno_con_vacante):
    turno, _ = turno_con_vacante
    turno.consolidado_en = reloj.ahora()
    sesion.flush()
    r = cliente.post(ruta(turno))
    assert r.status_code == 409
    assert r.json()["codigo"] == "TURNO_CONSOLIDADO"


def test_turno_guardado_sin_vacante_responde_409(cliente, sesion, como_coordinador, reloj):
    horario = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Ana").id)
    turno = guardar_turno(sesion, horario.id, date(2026, 10, 13))
    reloj.avanzar(timedelta(days=1))
    r = cliente.post(ruta(turno))
    assert r.status_code == 409
    assert r.json()["codigo"] == "TURNO_SIN_VACANTE"


def test_turno_calculado_sin_vacante_responde_409_y_no_guarda_nada(cliente, sesion, como_coordinador, reloj):
    horario = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Ana").id)
    reloj.avanzar(timedelta(days=1))
    r = cliente.post(f"/api/turnos/{horario.id}:2026-10-13/sin-cobertura")
    assert r.status_code == 409
    assert r.json()["codigo"] == "TURNO_SIN_VACANTE"
    assert sesion.scalar(select(func.count()).select_from(Turno)) == 0


def test_turno_que_no_existe_responde_404(cliente, sesion, como_coordinador):
    horario = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Ana").id)
    r = cliente.post(f"/api/turnos/{horario.id}:2026-10-14/sin-cobertura")  # miércoles: el horario es de martes
    assert r.status_code == 404
    assert r.json()["codigo"] == "TURNO_NO_ENCONTRADO"


def test_un_medico_no_marca_sin_cobertura(cliente, sesion, turno_con_vacante):
    turno, vacante = turno_con_vacante
    cliente.headers.update(encabezados(crear_usuario(sesion, "Beto")))
    r = cliente.post(ruta(turno))
    assert r.status_code == 403
    assert vacante.estado == EstadoVacante.ABIERTA

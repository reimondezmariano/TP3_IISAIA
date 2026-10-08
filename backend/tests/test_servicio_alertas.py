from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.modelos import EventoTurno, Notificacion, RolUsuario, TipoEventoTurno
from app.reloj import RelojFijo
from app.servicios.alertas import emitir_alertas
from app.servicios.consolidacion import ResultadoPuestaAlDia, ponerse_al_dia
from fabricas import abrir_vacante, bloqueado_hasta_commit, crear_horario_de_prueba, crear_usuario, guardar_turno

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
INICIO = datetime(2026, 10, 13, 8, 0, tzinfo=ZONA)  # turno del martes 13/10, 08:00 a 20:00


def preparar(sesion, vacante_desde=datetime(2026, 10, 9, 10, 0, tzinfo=ZONA)):
    ana = crear_usuario(sesion, "Ana")
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    turno = guardar_turno(sesion, crear_horario_de_prueba(sesion, ana.id).id, date(2026, 10, 13))
    abrir_vacante(sesion, turno, ana.id, vacante_desde)
    return ana, enzo, turno


def alertas(sesion, turno):
    return sorted(
        e.datos["umbral"]
        for e in sesion.scalars(
            select(EventoTurno).where(
                EventoTurno.turno_id == turno.id, EventoTurno.tipo == TipoEventoTurno.ALERTA_SIN_COBERTURA
            )
        )
    )


def test_a_las_48_h_avisa_a_los_coordinadores_y_no_a_los_medicos(sesion):
    ana, enzo, turno = preparar(sesion)
    otro = crear_usuario(sesion, "Otro coordinador", rol=RolUsuario.COORDINADOR)
    reloj = RelojFijo(INICIO - timedelta(hours=48))

    assert emitir_alertas(sesion, reloj, ZONA) == 1

    assert alertas(sesion, turno) == ["48H"]
    notificaciones = sesion.scalars(select(Notificacion).order_by(Notificacion.usuario_id)).all()
    assert [n.usuario_id for n in notificaciones] == [enzo.id, otro.id]
    assert all(n.tipo == "ALERTA_SIN_COBERTURA" and n.turno_id == turno.id for n in notificaciones)
    assert notificaciones[0].datos == {"umbral": "48H"}
    assert notificaciones[0].mensaje == "La guardia del 13/10 a las 08:00 sigue sin cobertura: empieza en 48 h."
    evento = sesion.scalars(select(EventoTurno)).one()
    assert evento.actor_id is None
    assert evento.ocurrido_en == reloj.ahora()


def test_no_repite_un_umbral(sesion):
    _, _, turno = preparar(sesion)
    reloj = RelojFijo(INICIO - timedelta(hours=47))
    emitir_alertas(sesion, reloj, ZONA)
    assert emitir_alertas(sesion, reloj, ZONA) == 0
    assert len(sesion.scalars(select(Notificacion)).all()) == 1


def test_si_vencieron_varios_umbrales_avisa_solo_el_mas_reciente(sesion):
    # Review Focus 3: reloj de demo adelantado o servidor caído.
    _, enzo, turno = preparar(sesion)
    reloj = RelojFijo(INICIO + timedelta(minutes=5))

    emitir_alertas(sesion, reloj, ZONA)

    assert alertas(sesion, turno) == ["24H", "48H", "INICIO"]
    [notificacion] = sesion.scalars(select(Notificacion)).all()
    assert notificacion.usuario_id == enzo.id
    assert notificacion.datos == {"umbral": "INICIO"}


def test_vacante_abierta_despues_de_un_umbral_no_lo_dispara(sesion):
    _, _, turno = preparar(sesion, vacante_desde=INICIO - timedelta(hours=30))
    assert emitir_alertas(sesion, RelojFijo(INICIO - timedelta(hours=29)), ZONA) == 0
    emitir_alertas(sesion, RelojFijo(INICIO - timedelta(hours=24)), ZONA)
    assert alertas(sesion, turno) == ["24H"]


def test_turno_sin_vacante_o_terminado_no_alerta(sesion):
    ana = crear_usuario(sesion, "Ana")
    crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    horario = crear_horario_de_prueba(sesion, ana.id)
    guardar_turno(sesion, horario.id, date(2026, 10, 13))  # sin vacante
    terminado = guardar_turno(sesion, horario.id, date(2026, 10, 6))
    abrir_vacante(sesion, terminado, ana.id, datetime(2026, 10, 1, tzinfo=ZONA))
    assert emitir_alertas(sesion, RelojFijo(INICIO), ZONA) == 0


def test_sin_coordinadores_registra_el_evento_igual(sesion):
    ana = crear_usuario(sesion, "Ana")
    turno = guardar_turno(sesion, crear_horario_de_prueba(sesion, ana.id).id, date(2026, 10, 13))
    abrir_vacante(sesion, turno, ana.id, datetime(2026, 10, 9, tzinfo=ZONA))
    emitir_alertas(sesion, RelojFijo(INICIO - timedelta(hours=48)), ZONA)
    assert alertas(sesion, turno) == ["48H"]
    assert sesion.scalars(select(Notificacion)).all() == []


def test_ponerse_al_dia_consolida_y_alerta(sesion, reloj):
    preparar(sesion)  # reloj: lunes 12/10 09:00, 23 h antes del inicio
    resultado = ponerse_al_dia(sesion, reloj, ZONA)
    assert resultado == ResultadoPuestaAlDia(consolidados=5, vacantes_sin_cobertura=0, alertas=1)


@pytest.mark.commit_real
def test_dos_pasadas_simultaneas_dejan_una_sola_alerta(fabrica_sesiones):
    # Review Focus 4: dos coordinadores consultando a la vez.
    reloj = RelojFijo(INICIO - timedelta(hours=48))
    with fabrica_sesiones() as s:
        preparar(s)
        s.commit()

    with fabrica_sesiones() as s1, fabrica_sesiones() as s2:
        assert emitir_alertas(s1, reloj, ZONA) == 1
        resultado = bloqueado_hasta_commit(s1, lambda: emitir_alertas(s2, reloj, ZONA))
        s2.commit()

    assert resultado == {"valor": 0}
    with fabrica_sesiones() as s:
        assert len(s.scalars(select(Notificacion)).all()) == 1

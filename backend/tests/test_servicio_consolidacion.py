from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.modelos import EstadoConsolidacion, EstadoUsuario, EstadoVacante, EventoTurno, TipoEventoTurno, Turno
from app.reloj import RelojFijo
from app.servicios.consolidacion import ResultadoConsolidacion, consolidar_pendientes
from fabricas import abrir_vacante, bloqueado_hasta_commit, crear_horario_de_prueba, crear_usuario, guardar_turno

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
MARTES_PASADOS = [date(2026, 9, 8), date(2026, 9, 15), date(2026, 9, 22), date(2026, 9, 29), date(2026, 10, 6)]


def turnos(sesion, horario_id):
    return sesion.scalars(select(Turno).where(Turno.horario_id == horario_id).order_by(Turno.fecha)).all()


def marca(sesion):
    return sesion.scalar(select(EstadoConsolidacion.consolidado_hasta))


def test_guarda_y_consolida_los_turnos_calculados_terminados(sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    horario = crear_horario_de_prueba(sesion, ana.id)

    resultado = consolidar_pendientes(sesion, reloj, ZONA)

    assert resultado == ResultadoConsolidacion(consolidados=5, vacantes_sin_cobertura=0)
    filas = turnos(sesion, horario.id)
    assert [t.fecha for t in filas] == MARTES_PASADOS
    assert all(t.realizador_id == ana.id and t.consolidado_en == reloj.ahora() for t in filas)
    assert filas[0].inicio == datetime(2026, 9, 8, 8, 0, tzinfo=ZONA)
    assert filas[0].fin == datetime(2026, 9, 8, 20, 0, tzinfo=ZONA)
    assert filas[0].titular_id == ana.id
    assert marca(sesion) == date(2026, 10, 12)


def test_es_idempotente(sesion, reloj):
    crear_horario_de_prueba(sesion, crear_usuario(sesion, "Ana").id)
    consolidar_pendientes(sesion, reloj, ZONA)
    assert consolidar_pendientes(sesion, reloj, ZONA) == ResultadoConsolidacion(0, 0)
    assert sesion.scalar(select(func.count()).select_from(Turno)) == 5


def test_turno_en_curso_no_se_consolida_y_la_marca_lo_espera(sesion, reloj):
    horario = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Ana").id)
    reloj.avanzar(timedelta(days=1, hours=1))  # martes 13/10 10:00: el turno de hoy está en curso

    consolidar_pendientes(sesion, reloj, ZONA)
    assert [t.fecha for t in turnos(sesion, horario.id)] == MARTES_PASADOS
    assert marca(sesion) == date(2026, 10, 13)

    reloj.avanzar(timedelta(hours=10))  # 20:00: terminó justo
    assert consolidar_pendientes(sesion, reloj, ZONA).consolidados == 1


def test_turno_que_cruza_medianoche_se_consolida_al_terminar(sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos")
    # domingo 20:00 a lunes 08:00, desde el domingo 11/10
    horario = crear_horario_de_prueba(sesion, carlos.id, dia=7, hora=time(20), dur=12, desde=date(2026, 10, 11))
    consolidar_pendientes(sesion, reloj, ZONA)
    [turno] = turnos(sesion, horario.id)
    assert turno.fecha == date(2026, 10, 11)
    assert turno.realizador_id == carlos.id


def test_horario_sin_titular_se_consolida_sin_realizador(sesion, reloj):
    horario = crear_horario_de_prueba(sesion, None)
    consolidar_pendientes(sesion, reloj, ZONA)
    assert all(t.realizador_id is None for t in turnos(sesion, horario.id))


def test_turno_guardado_con_asignado_lo_hace_el_asignado(sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    beto = crear_usuario(sesion, "Beto")
    horario = crear_horario_de_prueba(sesion, ana.id)
    guardado = guardar_turno(sesion, horario.id, date(2026, 10, 6), asignado_id=beto.id)

    resultado = consolidar_pendientes(sesion, reloj, ZONA)

    assert resultado.consolidados == 5  # 4 calculados + el guardado; el calculado del 6/10 no se duplica
    assert guardado.realizador_id == beto.id
    assert guardado.consolidado_en == reloj.ahora()


def test_turno_guardado_usa_su_foto_y_no_la_plantilla(sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    beto = crear_usuario(sesion, "Beto")
    horario = crear_horario_de_prueba(sesion, ana.id)
    guardado = guardar_turno(sesion, horario.id, date(2026, 10, 6))
    guardado.titular_id = beto.id  # la foto (D11) difiere de la plantilla actual
    sesion.flush()
    consolidar_pendientes(sesion, reloj, ZONA)
    assert guardado.realizador_id == beto.id


def test_vacante_abierta_al_terminar_queda_sin_cobertura(sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    horario = crear_horario_de_prueba(sesion, ana.id)
    guardado = guardar_turno(sesion, horario.id, date(2026, 10, 6))
    vacante = abrir_vacante(sesion, guardado, ana.id, datetime(2026, 10, 1, 10, 0, tzinfo=ZONA))

    resultado = consolidar_pendientes(sesion, reloj, ZONA)

    assert resultado.vacantes_sin_cobertura == 1
    assert guardado.realizador_id is None
    assert guardado.sin_cobertura_en == reloj.ahora()
    assert vacante.estado == EstadoVacante.SIN_COBERTURA
    assert vacante.cerrada_en == reloj.ahora()
    [evento] = sesion.scalars(select(EventoTurno).where(EventoTurno.turno_id == guardado.id)).all()
    assert evento.tipo == TipoEventoTurno.TURNO_SIN_COBERTURA
    assert evento.actor_id is None
    assert evento.datos == {"vacante_id": vacante.id, "al_consolidar": True}


def test_horario_cerrado_solo_consolida_su_vigencia(sesion, reloj):
    horario = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Ana").id, hasta=date(2026, 9, 20))
    consolidar_pendientes(sesion, reloj, ZONA)
    assert [t.fecha for t in turnos(sesion, horario.id)] == [date(2026, 9, 8), date(2026, 9, 15)]


def test_sin_horarios_no_hace_nada(sesion, reloj):
    assert consolidar_pendientes(sesion, reloj, ZONA) == ResultadoConsolidacion(0, 0)


@pytest.mark.commit_real
def test_dos_consolidaciones_simultaneas_dejan_una_fila_por_turno(fabrica_sesiones):
    # Review Focus 4.
    reloj = RelojFijo(datetime(2026, 10, 12, 9, 0, tzinfo=ZONA))
    with fabrica_sesiones() as s:
        crear_horario_de_prueba(s, crear_usuario(s, "Ana").id)
        s.commit()

    with fabrica_sesiones() as s1, fabrica_sesiones() as s2:
        primera = consolidar_pendientes(s1, reloj, ZONA)
        resultado = bloqueado_hasta_commit(s1, lambda: consolidar_pendientes(s2, reloj, ZONA))
        s2.commit()

    assert primera.consolidados == 5
    assert resultado == {"valor": ResultadoConsolidacion(0, 0)}
    with fabrica_sesiones() as s:
        assert s.scalar(select(func.count()).select_from(Turno)) == 5


def test_titular_o_asignado_dado_de_baja_antes_del_turno_no_es_realizador(sesion, reloj):
    # D24: después de su fecha de baja no hace guardias, aunque el turno guardado conserve su foto (D11).
    ana = crear_usuario(sesion, "Ana")
    beto = crear_usuario(sesion, "Beto")
    horario = crear_horario_de_prueba(sesion, ana.id)
    de_titular = guardar_turno(sesion, horario.id, date(2026, 10, 6))
    de_asignado = guardar_turno(sesion, horario.id, date(2026, 9, 29), asignado_id=beto.id)
    del_ultimo_dia = guardar_turno(sesion, horario.id, date(2026, 9, 22))
    ana.estado, ana.fecha_baja = EstadoUsuario.BAJA, date(2026, 9, 22)  # su último día es el 22/9
    beto.estado, beto.fecha_baja = EstadoUsuario.BAJA, date(2026, 9, 28)
    sesion.flush()

    consolidar_pendientes(sesion, reloj, ZONA)

    assert de_titular.realizador_id is None
    assert de_asignado.realizador_id is None
    assert del_ultimo_dia.realizador_id == ana.id

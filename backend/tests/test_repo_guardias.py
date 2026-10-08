from datetime import date, datetime, time

from sqlalchemy import update

from app.dominio.equidad import TurnoDelMes
from app.modelos import EstadoVacante, Turno, Vacante, VersionHorario
from app.repos.guardias import guardias_del_medico, turnos_del_mes
from fabricas import ZONA, crear_horario_de_prueba, crear_usuario, guardar_turno

# El horario de prueba es el martes de 08:00 a 20:00. Se evalúa una postulación al martes 20/10 de 22:00 a 23:00
# de otro horario, para que la ventana incluya el turno del martes 13/10 y el del 20/10.
MARTES_13 = (datetime(2026, 10, 13, 8, tzinfo=ZONA), datetime(2026, 10, 13, 20, tzinfo=ZONA))


def instante(dia, hora, mes=10):
    return datetime(2026, mes, dia, hora, tzinfo=ZONA)


def guardias(sesion, medico, desde, hasta, excluir="0:2000-01-01"):
    return [(g.inicio, g.fin) for g in guardias_del_medico(sesion, medico.id, desde, hasta, excluir, ZONA)]


def abrir_vacante(sesion, turno, autor):
    sesion.add(
        Vacante(turno_id=turno.id, generada_por_id=autor.id, creada_en=instante(12, 9), estado=EstadoVacante.ABIERTA)
    )
    sesion.flush()


def test_incluye_el_turno_calculado_del_titular(sesion):
    carlos = crear_usuario(sesion, "Carlos")
    crear_horario_de_prueba(sesion, carlos.id)
    assert guardias(sesion, carlos, instante(13, 10), instante(13, 14)) == [MARTES_13]


def test_no_incluye_los_turnos_de_otro_titular(sesion):
    carlos, paula = crear_usuario(sesion, "Carlos"), crear_usuario(sesion, "Paula")
    crear_horario_de_prueba(sesion, carlos.id)
    assert guardias(sesion, paula, instante(13, 10), instante(13, 14)) == []


def test_un_turno_con_vacante_abierta_no_cuenta_para_el_titular(sesion):
    carlos = crear_usuario(sesion, "Carlos")
    horario = crear_horario_de_prueba(sesion, carlos.id)
    abrir_vacante(sesion, guardar_turno(sesion, horario.id, date(2026, 10, 13)), carlos)
    assert guardias(sesion, carlos, instante(13, 10), instante(13, 14)) == []


def test_un_turno_asignado_a_otro_no_cuenta_para_el_titular_y_si_para_el_asignado(sesion):
    carlos, paula = crear_usuario(sesion, "Carlos"), crear_usuario(sesion, "Paula")
    horario = crear_horario_de_prueba(sesion, carlos.id)
    guardar_turno(sesion, horario.id, date(2026, 10, 13), asignado_id=paula.id)
    assert guardias(sesion, carlos, instante(13, 10), instante(13, 14)) == []
    assert guardias(sesion, paula, instante(13, 10), instante(13, 14)) == [MARTES_13]


def test_usa_la_foto_guardada_y_no_la_plantilla_actual(sesion):
    carlos = crear_usuario(sesion, "Carlos")
    horario = crear_horario_de_prueba(sesion, carlos.id)
    guardar_turno(sesion, horario.id, date(2026, 10, 13))  # foto: 08:00 a 20:00
    sesion.execute(update(VersionHorario).where(VersionHorario.horario_id == horario.id).values(hora_inicio=time(9)))
    sesion.expire_all()

    assert guardias(sesion, carlos, instante(13, 10), instante(13, 14)) == [MARTES_13]  # D11, D12
    # el martes siguiente, sin fila, sale de la plantilla ya cambiada
    assert guardias(sesion, carlos, instante(20, 10), instante(20, 14)) == [(instante(20, 9), instante(20, 21))]


def test_excluye_el_turno_evaluado(sesion):
    carlos = crear_usuario(sesion, "Carlos")
    horario = crear_horario_de_prueba(sesion, carlos.id)
    excluido = f"{horario.id}:2026-10-13"
    assert guardias(sesion, carlos, instante(13, 10), instante(13, 14), excluir=excluido) == []


def test_incluye_la_guardia_que_cruza_medianoche_desde_el_dia_anterior(sesion):
    carlos = crear_usuario(sesion, "Carlos")
    crear_horario_de_prueba(sesion, carlos.id, dia=5, hora=time(20), dur=12)  # viernes 20:00 a sábado 08:00
    assert guardias(sesion, carlos, instante(17, 2), instante(17, 6)) == [(instante(16, 20), instante(17, 8))]


def test_no_incluye_guardias_que_solo_se_tocan_en_el_borde(sesion):
    carlos = crear_usuario(sesion, "Carlos")
    crear_horario_de_prueba(sesion, carlos.id)  # martes 08:00 a 20:00
    assert guardias(sesion, carlos, instante(13, 20), instante(13, 23)) == []
    assert guardias(sesion, carlos, instante(13, 5), instante(13, 8)) == []


# --- turnos del mes (D17) ---


def test_turnos_del_mes_respeta_la_zona_del_servicio(sesion):
    carlos, paula = crear_usuario(sesion, "Carlos"), crear_usuario(sesion, "Paula")
    horario = crear_horario_de_prueba(sesion, carlos.id, dia=6, hora=time(22), dur=6)  # sábado 22:00 a 04:00
    guardar_turno(sesion, horario.id, date(2026, 10, 31), asignado_id=paula.id)  # 22:00 -03:00 = 01:00 UTC del 1/11

    octubre = turnos_del_mes(sesion, 2026, 10, ZONA)
    noviembre = turnos_del_mes(sesion, 2026, 11, ZONA)

    assert octubre == [TurnoDelMes(instante(31, 22), paula.id, carlos.id)]
    assert noviembre == []


def test_turnos_del_mes_ignora_otros_meses(sesion):
    carlos = crear_usuario(sesion, "Carlos")
    horario = crear_horario_de_prueba(sesion, carlos.id)
    for dia in (date(2026, 9, 29), date(2026, 10, 6), date(2026, 11, 3)):
        guardar_turno(sesion, horario.id, dia)
    assert [t.inicio.date() for t in turnos_del_mes(sesion, 2026, 10, ZONA)] == [date(2026, 10, 6)]

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.dominio.alertas import Umbral
from app.dominio.notificaciones import TipoNotificacion, mensaje_alerta
from app.modelos import EstadoUsuario, Notificacion, RolUsuario
from app.servicios.notificaciones import destinatarios, notificar
from fabricas import HOY, crear_horario_de_prueba, crear_usuario, guardar_turno

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
AHORA = datetime(2026, 10, 12, 9, 0, tzinfo=ZONA)


def test_mensaje_alerta_por_umbral():
    inicio = datetime(2026, 10, 17, 8, 0, tzinfo=ZONA)
    assert mensaje_alerta(Umbral.HORAS_48, inicio) == "La guardia del 17/10 a las 08:00 sigue sin cobertura: empieza en 48 h."
    assert mensaje_alerta(Umbral.HORAS_24, inicio) == "La guardia del 17/10 a las 08:00 sigue sin cobertura: empieza en 24 h."
    assert mensaje_alerta(Umbral.INICIO, inicio) == "La guardia del 17/10 a las 08:00 sigue sin cobertura: ya empezó."


def test_notificar_crea_una_por_destinatario_sin_repetir(sesion):
    ana = crear_usuario(sesion, "Ana")
    beto = crear_usuario(sesion, "Beto")
    creadas = notificar(sesion, [ana.id, beto.id, ana.id], TipoNotificacion.VACANTE_URGENTE, "Hola", AHORA)
    assert sorted(n.usuario_id for n in creadas) == sorted([ana.id, beto.id])
    filas = sesion.scalars(select(Notificacion)).all()
    assert len(filas) == 2
    assert all(n.tipo == "VACANTE_URGENTE" and n.creada_en == AHORA and n.leida_en is None for n in filas)


def test_notificar_guarda_turno_y_datos(sesion):
    ana = crear_usuario(sesion, "Ana")
    turno = guardar_turno(sesion, crear_horario_de_prueba(sesion, ana.id).id, date(2026, 10, 13))
    [n] = notificar(
        sesion, [ana.id], TipoNotificacion.ALERTA_SIN_COBERTURA, "x", AHORA, turno=turno, datos={"umbral": "48H"}
    )
    assert n.turno_id == turno.id
    assert n.datos == {"umbral": "48H"}


def test_notificar_sin_destinatarios_no_crea_nada(sesion):
    assert notificar(sesion, [], TipoNotificacion.VACANTE_URGENTE, "x", AHORA) == []


def test_notificar_rechaza_instante_sin_zona(sesion):
    ana = crear_usuario(sesion, "Ana")
    with pytest.raises(ValueError):
        notificar(sesion, [ana.id], TipoNotificacion.VACANTE_URGENTE, "x", datetime(2026, 10, 12, 9))


def test_destinatarios_son_los_que_tienen_acceso_ese_dia(sesion):
    activo = crear_usuario(sesion, "Activo")
    baja_hoy = crear_usuario(sesion, "Baja hoy", estado=EstadoUsuario.BAJA, fecha_baja=HOY)
    crear_usuario(sesion, "Baja vieja", estado=EstadoUsuario.BAJA)
    crear_usuario(sesion, "Pendiente", estado=EstadoUsuario.PENDIENTE)
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    assert destinatarios(sesion, RolUsuario.MEDICO, HOY) == sorted([activo.id, baja_hoy.id])
    assert destinatarios(sesion, RolUsuario.COORDINADOR, HOY) == [enzo.id]
    assert destinatarios(sesion, RolUsuario.MEDICO, HOY, excepto={activo.id}) == [baja_hoy.id]

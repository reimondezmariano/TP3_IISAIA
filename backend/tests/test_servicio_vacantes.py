from datetime import date, timedelta

import pytest
from sqlalchemy import func, select, update

from app.errores import ErrorDominio
from app.modelos import (
    EstadoUsuario,
    EstadoVacante,
    EventoTurno,
    Notificacion,
    RolUsuario,
    TipoEventoTurno,
    Turno,
    Vacante,
)
from app.servicios.vacantes import generar_vacante
from fabricas import ZONA, bloqueado_hasta_commit, crear_horario_de_prueba, crear_usuario, guardar_turno

# Reloj de prueba: lunes 12/10/2026 09:00. El turno del martes 13/10 08:00 está a 23 h (urgente);
# el del martes 20/10 está a más de 24 h.
URGENTE = "2026-10-13"
LEJANO = "2026-10-20"


def generar(sesion, reloj, horario_id, fecha, actor, motivo=None):
    return generar_vacante(sesion, f"{horario_id}:{fecha}", actor, motivo, reloj, ZONA)


def eventos(sesion, turno_id):
    return list(sesion.scalars(select(EventoTurno).where(EventoTurno.turno_id == turno_id).order_by(EventoTurno.id)))


def test_el_titular_genera_la_vacante(sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos")
    horario = crear_horario_de_prueba(sesion, carlos.id)

    resultado = generar(sesion, reloj, horario.id, LEJANO, carlos, "Congreso")

    vacante = resultado.vacante
    assert (vacante.estado, vacante.motivo, vacante.generada_por_id) == (EstadoVacante.ABIERTA, "Congreso", carlos.id)
    assert vacante.creada_en == reloj.ahora() and vacante.cerrada_en is None
    assert resultado.turno.id == vacante.turno_id and resultado.urgente is False


def test_el_evento_queda_con_actor_y_datos(sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos")
    horario = crear_horario_de_prueba(sesion, carlos.id)

    resultado = generar(sesion, reloj, horario.id, LEJANO, carlos)

    [evento] = eventos(sesion, resultado.turno.id)
    assert (evento.tipo, evento.actor_id, evento.ocurrido_en) == (
        TipoEventoTurno.VACANTE_GENERADA,
        carlos.id,
        reloj.ahora(),
    )
    assert evento.datos == {"urgente": False, "asignado_anterior_id": None, "vacante_id": resultado.vacante.id}


def test_con_asignado_lo_borra_y_lo_deja_en_el_evento(sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos")
    paula = crear_usuario(sesion, "Paula")
    horario = crear_horario_de_prueba(sesion, carlos.id)
    guardar_turno(sesion, horario.id, date(2026, 10, 20), asignado_id=paula.id)

    resultado = generar(sesion, reloj, horario.id, LEJANO, paula)  # D31: la genera el asignado

    assert resultado.turno.asignado_id is None
    assert resultado.asignado_anterior_id == paula.id
    [evento] = eventos(sesion, resultado.turno.id)
    assert evento.datos["asignado_anterior_id"] == paula.id


def test_vacante_con_menos_de_24_h_es_urgente_y_notifica_a_los_medicos_activos(sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos")
    mariano = crear_usuario(sesion, "Mariano")
    florencia = crear_usuario(sesion, "Florencia")
    crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    crear_usuario(sesion, "Nuevo", estado=EstadoUsuario.PENDIENTE)
    horario = crear_horario_de_prueba(sesion, carlos.id)

    resultado = generar(sesion, reloj, horario.id, URGENTE, carlos)

    assert resultado.urgente is True
    [evento] = eventos(sesion, resultado.turno.id)
    assert evento.datos["urgente"] is True
    notificaciones = list(sesion.scalars(select(Notificacion)))
    assert {n.usuario_id for n in notificaciones} == {mariano.id, florencia.id}
    assert {n.tipo for n in notificaciones} == {"VACANTE_URGENTE"}
    assert all(n.turno_id == resultado.turno.id and n.creada_en == reloj.ahora() for n in notificaciones)


def test_vacante_con_mas_de_24_h_no_notifica(sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos")
    crear_usuario(sesion, "Mariano")
    horario = crear_horario_de_prueba(sesion, carlos.id)

    generar(sesion, reloj, horario.id, LEJANO, carlos)

    assert sesion.scalar(select(func.count()).select_from(Notificacion)) == 0


def test_un_tercero_no_puede_generar(sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos")
    tercero = crear_usuario(sesion, "Tercero")
    horario = crear_horario_de_prueba(sesion, carlos.id)

    with pytest.raises(ErrorDominio) as error:
        generar(sesion, reloj, horario.id, LEJANO, tercero)

    assert (error.value.codigo, error.value.status) == ("SIN_PERMISO", 403)


def test_el_coordinador_puede_generar_en_un_turno_sin_titular(sesion, reloj):
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    horario = crear_horario_de_prueba(sesion, None)

    resultado = generar(sesion, reloj, horario.id, LEJANO, enzo)

    assert resultado.vacante.generada_por_id == enzo.id and resultado.turno.titular_id is None


def test_un_medico_no_puede_generar_en_un_turno_sin_titular(sesion, reloj):
    horario = crear_horario_de_prueba(sesion, None)
    with pytest.raises(ErrorDominio) as error:
        generar(sesion, reloj, horario.id, LEJANO, crear_usuario(sesion, "Mariano"))
    assert error.value.codigo == "SIN_PERMISO"


def test_turno_empezado_responde_409(sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos")
    horario = crear_horario_de_prueba(sesion, carlos.id)
    reloj.avanzar(timedelta(days=1))  # martes 13/10 09:00: el turno de las 08:00 ya empezó

    with pytest.raises(ErrorDominio) as error:
        generar(sesion, reloj, horario.id, URGENTE, carlos)

    assert (error.value.codigo, error.value.status) == ("TURNO_YA_EMPEZO", 409)


def test_segunda_vacante_abierta_responde_409(sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos")
    horario = crear_horario_de_prueba(sesion, carlos.id)
    generar(sesion, reloj, horario.id, LEJANO, carlos)

    with pytest.raises(ErrorDominio) as error:
        generar(sesion, reloj, horario.id, LEJANO, carlos)

    assert (error.value.codigo, error.value.status) == ("VACANTE_YA_ABIERTA", 409)


def test_se_puede_generar_otra_despues_de_retirar_la_primera(sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos")
    horario = crear_horario_de_prueba(sesion, carlos.id)
    primera = generar(sesion, reloj, horario.id, LEJANO, carlos).vacante
    sesion.execute(
        update(Vacante)
        .where(Vacante.id == primera.id)
        .values(estado=EstadoVacante.RETIRADA, cerrada_en=reloj.ahora())
    )
    sesion.expire_all()

    segunda = generar(sesion, reloj, horario.id, LEJANO, carlos).vacante

    assert segunda.id != primera.id and segunda.estado == EstadoVacante.ABIERTA


def test_turno_inexistente_responde_404_y_no_guarda_nada(sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos")
    horario = crear_horario_de_prueba(sesion, carlos.id)

    with pytest.raises(ErrorDominio) as error:
        generar(sesion, reloj, horario.id, "2026-10-21", carlos)  # miércoles

    assert error.value.codigo == "TURNO_NO_ENCONTRADO"
    assert sesion.scalar(select(func.count()).select_from(Turno)) == 0


def test_un_turno_consolidado_no_admite_vacante(sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos")
    horario = crear_horario_de_prueba(sesion, carlos.id)
    guardar_turno(sesion, horario.id, date(2026, 10, 20), consolidado_en=reloj.ahora())

    with pytest.raises(ErrorDominio) as error:
        generar(sesion, reloj, horario.id, LEJANO, carlos)

    assert error.value.codigo == "TURNO_YA_EMPEZO"


@pytest.mark.commit_real
def test_dos_generaciones_simultaneas_una_gana(fabrica_sesiones, reloj):
    with fabrica_sesiones() as s:
        carlos = crear_usuario(s, "Carlos")
        horario_id = crear_horario_de_prueba(s, carlos.id).id
        s.commit()
        carlos_id = carlos.id

    with fabrica_sesiones() as s1, fabrica_sesiones() as s2:
        actor1 = s1.get(type(carlos), carlos_id)
        actor2 = s2.get(type(carlos), carlos_id)
        generar(s1, reloj, horario_id, LEJANO, actor1)
        resultado = bloqueado_hasta_commit(s1, lambda: generar(s2, reloj, horario_id, LEJANO, actor2))

    assert isinstance(resultado.get("error"), ErrorDominio)
    assert resultado["error"].codigo == "VACANTE_YA_ABIERTA"
    with fabrica_sesiones() as s:
        assert s.scalar(select(func.count()).select_from(Vacante)) == 1
        assert s.scalar(select(func.count()).select_from(EventoTurno)) == 1

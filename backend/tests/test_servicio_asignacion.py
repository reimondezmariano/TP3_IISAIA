from datetime import date, time, timedelta

import pytest
from sqlalchemy import func, select

from app.dominio.asignacion import CasoAsignacion
from app.errores import ErrorDominio
from app.modelos import (
    EstadoUsuario,
    EstadoVacante,
    EventoTurno,
    Notificacion,
    Postulacion,
    RolUsuario,
    TipoEventoTurno,
    Turno,
    Usuario,
    Vacante,
)
from app.servicios.asignacion import asignar
from app.servicios.postulaciones import postular
from app.servicios.sin_cobertura import marcar_sin_cobertura
from app.servicios.vacantes import generar_vacante
from fabricas import ZONA, bloqueado_hasta_commit, crear_horario_de_prueba, crear_usuario, guardar_turno

# Reloj de prueba: lunes 12/10/2026 09:00. El turno de prueba es el martes 20/10 de 08:00 a 20:00.
FECHA = "2026-10-20"


@pytest.fixture
def escena(sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos")
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    horario = crear_horario_de_prueba(sesion, carlos.id)
    turno_id = f"{horario.id}:{FECHA}"
    vacante = generar_vacante(sesion, turno_id, carlos, "Congreso", reloj, ZONA).vacante
    return carlos, enzo, horario, turno_id, vacante


def asignar_a(sesion, reloj, turno_id, medico, coordinador, reasignar=False):
    return asignar(sesion, turno_id, medico.id, reasignar, coordinador, reloj, ZONA)


def postulados(sesion, reloj, turno_id, *nombres):
    medicos = []
    for nombre in nombres:
        medico = crear_usuario(sesion, nombre)
        postular(sesion, turno_id, medico, reloj, ZONA)
        reloj.avanzar(timedelta(minutes=1))
        medicos.append(medico)
    return medicos


def ultimo_evento(sesion, tipo):
    return sesion.scalars(select(EventoTurno).where(EventoTurno.tipo == tipo).order_by(EventoTurno.id.desc())).first()


def error_de(sesion, reloj, turno_id, medico, coordinador, **kwargs):
    with pytest.raises(ErrorDominio) as error:
        asignar_a(sesion, reloj, turno_id, medico, coordinador, **kwargs)
    return error.value


def test_elige_a_un_candidato_y_registra_posicion_y_cantidad(sesion, reloj, escena):
    _, enzo, _, turno_id, _ = escena
    ana, beto = postulados(sesion, reloj, turno_id, "Ana", "Beto")

    resultado = asignar_a(sesion, reloj, turno_id, ana, enzo)

    assert resultado.caso is CasoAsignacion.CANDIDATO_ELEGIDO and resultado.turno.asignado_id == ana.id
    evento = ultimo_evento(sesion, TipoEventoTurno.CANDIDATO_ELEGIDO)
    assert (evento.actor_id, evento.ocurrido_en) == (enzo.id, reloj.ahora())
    assert evento.datos == {"posicion": 1, "candidatos": 2, "asignado_id": ana.id}
    assert beto.id  # el otro candidato no cambia


def test_el_coordinador_puede_elegir_al_ultimo_de_la_lista(sesion, reloj, escena):
    _, enzo, _, turno_id, _ = escena
    _, _, cleo = postulados(sesion, reloj, turno_id, "Ana", "Beto", "Cleo")

    resultado = asignar_a(sesion, reloj, turno_id, cleo, enzo)

    assert resultado.caso is CasoAsignacion.CANDIDATO_ELEGIDO
    assert ultimo_evento(sesion, TipoEventoTurno.CANDIDATO_ELEGIDO).datos["posicion"] == 3


def test_asignacion_directa_de_quien_no_se_postulo(sesion, reloj, escena):
    _, enzo, _, turno_id, _ = escena
    dana = crear_usuario(sesion, "Dana")

    resultado = asignar_a(sesion, reloj, turno_id, dana, enzo)

    assert resultado.caso is CasoAsignacion.ASIGNACION_DIRECTA and resultado.turno.asignado_id == dana.id
    assert ultimo_evento(sesion, TipoEventoTurno.ASIGNACION_DIRECTA).datos == {"asignado_id": dana.id}


def test_cierra_la_vacante_como_cubierta(sesion, reloj, escena):
    _, enzo, _, turno_id, vacante = escena
    reloj.avanzar(timedelta(hours=1))

    resultado = asignar_a(sesion, reloj, turno_id, crear_usuario(sesion, "Dana"), enzo)

    assert resultado.vacante.id == vacante.id
    assert (vacante.estado, vacante.cerrada_en) == (EstadoVacante.CUBIERTA, reloj.ahora())


def test_reasignar_pide_reasignar_true_y_registra_al_anterior(sesion, reloj, escena):
    _, enzo, _, turno_id, _ = escena
    ana, beto = crear_usuario(sesion, "Ana"), crear_usuario(sesion, "Beto")
    asignar_a(sesion, reloj, turno_id, ana, enzo)

    sin_reasignar = error_de(sesion, reloj, turno_id, beto, enzo)
    resultado = asignar_a(sesion, reloj, turno_id, beto, enzo, reasignar=True)

    assert (sin_reasignar.codigo, sin_reasignar.status) == ("YA_TIENE_ASIGNADO", 409)
    assert resultado.caso is CasoAsignacion.REASIGNACION and resultado.turno.asignado_id == beto.id
    assert ultimo_evento(sesion, TipoEventoTurno.REASIGNACION).datos == {
        "asignado_id": beto.id,
        "asignado_anterior_id": ana.id,
    }


def test_asignar_a_quien_ya_esta_asignado_responde_409(sesion, reloj, escena):
    _, enzo, _, turno_id, _ = escena
    ana = crear_usuario(sesion, "Ana")
    asignar_a(sesion, reloj, turno_id, ana, enzo)
    error = error_de(sesion, reloj, turno_id, ana, enzo, reasignar=True)
    assert (error.codigo, error.status) == ("YA_ASIGNADO", 409)


def test_asignar_a_un_turno_sin_titular_no_necesita_vacante(sesion, reloj):
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    ana = crear_usuario(sesion, "Ana")
    horario = crear_horario_de_prueba(sesion, None)

    resultado = asignar_a(sesion, reloj, f"{horario.id}:{FECHA}", ana, enzo)

    assert resultado.turno.asignado_id == ana.id and resultado.vacante is None


def test_un_turno_con_titular_y_sin_vacante_responde_409(sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos")
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    horario = crear_horario_de_prueba(sesion, carlos.id)
    error = error_de(sesion, reloj, f"{horario.id}:{FECHA}", crear_usuario(sesion, "Ana"), enzo)
    assert (error.codigo, error.status) == ("TURNO_SIN_VACANTE", 409)


@pytest.mark.parametrize(
    ("rol", "estado"),
    [(RolUsuario.COORDINADOR, EstadoUsuario.ACTIVO), (RolUsuario.MEDICO, EstadoUsuario.PENDIENTE)],
)
def test_no_asigna_a_un_coordinador_ni_a_un_pendiente(sesion, reloj, escena, rol, estado):
    _, enzo, _, turno_id, _ = escena
    intruso = crear_usuario(sesion, "Intruso", rol=rol, estado=estado)
    error = error_de(sesion, reloj, turno_id, intruso, enzo)
    assert (error.codigo, error.status) == ("NO_HABILITADO", 422)


def test_no_asigna_al_titular(sesion, reloj, escena):
    carlos, enzo, _, turno_id, _ = escena
    error = error_de(sesion, reloj, turno_id, carlos, enzo)
    assert (error.codigo, error.status) == ("ES_TITULAR", 422)


def test_no_asigna_con_una_guardia_superpuesta(sesion, reloj, escena):
    _, enzo, _, turno_id, _ = escena
    ana = crear_usuario(sesion, "Ana")
    crear_horario_de_prueba(sesion, ana.id, hora=time(10), dur=4)  # su propio martes 10:00 a 14:00
    error = error_de(sesion, reloj, turno_id, ana, enzo)
    assert (error.codigo, error.status) == ("GUARDIA_SUPERPUESTA", 422)


def test_no_asigna_a_un_baja_despues_de_su_fecha_de_baja(sesion, reloj, escena):
    _, enzo, _, turno_id, _ = escena
    despues = crear_usuario(sesion, "Baja el 19", estado=EstadoUsuario.BAJA, fecha_baja=date(2026, 10, 19))
    hasta = crear_usuario(sesion, "Baja el 20", estado=EstadoUsuario.BAJA, fecha_baja=date(2026, 10, 20))

    assert error_de(sesion, reloj, turno_id, despues, enzo).codigo == "NO_HABILITADO"
    assert asignar_a(sesion, reloj, turno_id, hasta, enzo).turno.asignado_id == hasta.id


def test_turno_terminado_responde_409(sesion, reloj, escena):
    _, enzo, _, turno_id, _ = escena
    reloj.avanzar(timedelta(days=8, hours=12))  # martes 20/10 21:00: el turno terminó a las 20:00
    error = error_de(sesion, reloj, turno_id, crear_usuario(sesion, "Ana"), enzo)
    assert (error.codigo, error.status) == ("TURNO_TERMINADO", 409)


def test_se_puede_asignar_con_el_turno_en_curso(sesion, reloj, escena):
    _, enzo, _, turno_id, _ = escena
    reloj.avanzar(timedelta(days=8, hours=2))  # 20/10 11:00: empezó pero no terminó (D19)
    assert asignar_a(sesion, reloj, turno_id, crear_usuario(sesion, "Ana"), enzo).turno.asignado_id is not None


def test_un_medico_no_puede_asignar(sesion, reloj, escena):
    carlos, _, _, turno_id, _ = escena
    error = error_de(sesion, reloj, turno_id, crear_usuario(sesion, "Ana"), carlos)
    assert (error.codigo, error.status) == ("SIN_PERMISO", 403)


def test_medico_o_turno_inexistente_responde_404(sesion, reloj, escena):
    _, enzo, horario, turno_id, _ = escena
    with pytest.raises(ErrorDominio) as sin_medico:
        asignar(sesion, turno_id, 99999, False, enzo, reloj, ZONA)
    sin_turno = error_de(sesion, reloj, f"{horario.id}:2026-10-21", crear_usuario(sesion, "Ana"), enzo)
    assert (sin_medico.value.codigo, sin_medico.value.status) == ("USUARIO_NO_ENCONTRADO", 404)
    assert sin_turno.codigo == "TURNO_NO_ENCONTRADO"


def test_las_postulaciones_sobreviven_a_la_asignacion(sesion, reloj, escena):
    _, enzo, _, turno_id, _ = escena
    ana, beto = postulados(sesion, reloj, turno_id, "Ana", "Beto")

    asignar_a(sesion, reloj, turno_id, ana, enzo)

    activas = sesion.scalars(select(Postulacion).where(Postulacion.retirada_en.is_(None))).all()
    assert {p.medico_id for p in activas} == {ana.id, beto.id}  # D16: son la reserva


def test_avisa_al_asignado_con_la_funcion_de_notificaciones(sesion, reloj, escena):
    _, enzo, _, turno_id, _ = escena
    ana = crear_usuario(sesion, "Ana")

    asignar_a(sesion, reloj, turno_id, ana, enzo)

    avisos = list(sesion.scalars(select(Notificacion).where(Notificacion.tipo == "TURNO_ASIGNADO")))
    assert [(n.usuario_id, n.creada_en) for n in avisos] == [(ana.id, reloj.ahora())]
    assert avisos[0].datos == {"turnoId": turno_id, "caso": "ASIGNACION_DIRECTA"}
    assert "20/10" in avisos[0].mensaje and "08:00" in avisos[0].mensaje


def test_asignar_un_turno_sin_cobertura_levanta_la_marca(sesion, reloj, escena):
    carlos, enzo, _, turno_id, vacante = escena
    reloj.avanzar(timedelta(days=8, hours=1))  # 20/10 10:00: el turno empezó y nadie lo cubrió
    turno, _ = marcar_sin_cobertura(sesion, turno_id, enzo, reloj, ZONA)
    assert turno.sin_cobertura_en is not None and vacante.estado == EstadoVacante.SIN_COBERTURA
    reloj.avanzar(timedelta(hours=1))

    resultado = asignar_a(sesion, reloj, turno_id, crear_usuario(sesion, "Ana"), enzo)

    assert resultado.turno.sin_cobertura_en is None  # regla de Florencia, misma transacción
    assert (vacante.estado, vacante.cerrada_en) == (EstadoVacante.CUBIERTA, reloj.ahora())
    assert ultimo_evento(sesion, TipoEventoTurno.ASIGNACION_DIRECTA).datos["sin_cobertura_levantada"] is True


def test_un_turno_ya_consolidado_no_se_asigna(sesion, reloj, escena):
    _, enzo, horario, _, _ = escena
    turno = guardar_turno(sesion, horario.id, date(2026, 10, 13), consolidado_en=reloj.ahora())
    error = error_de(sesion, reloj, f"{horario.id}:2026-10-13", crear_usuario(sesion, "Ana"), enzo)
    assert error.codigo == "TURNO_TERMINADO" and turno.id


@pytest.mark.commit_real
def test_dos_asignaciones_simultaneas_una_gana(fabrica_sesiones, reloj):
    with fabrica_sesiones() as s:
        carlos = crear_usuario(s, "Carlos")
        enzo = crear_usuario(s, "Enzo", rol=RolUsuario.COORDINADOR)
        ana, beto = crear_usuario(s, "Ana"), crear_usuario(s, "Beto")
        horario = crear_horario_de_prueba(s, carlos.id)
        turno_id = f"{horario.id}:{FECHA}"
        generar_vacante(s, turno_id, carlos, None, reloj, ZONA)
        s.commit()
        enzo_id, ana_id, beto_id = enzo.id, ana.id, beto.id

    with fabrica_sesiones() as s1, fabrica_sesiones() as s2:
        asignar(s1, turno_id, ana_id, False, s1.get(Usuario, enzo_id), reloj, ZONA)
        resultado = bloqueado_hasta_commit(
            s1, lambda: asignar(s2, turno_id, beto_id, False, s2.get(Usuario, enzo_id), reloj, ZONA)
        )

    assert isinstance(resultado.get("error"), ErrorDominio)
    assert resultado["error"].codigo == "YA_TIENE_ASIGNADO"
    with fabrica_sesiones() as s:
        assert s.scalar(select(Turno.asignado_id)) == ana_id


@pytest.mark.commit_real
def test_postulacion_y_asignacion_simultaneas_no_dejan_estado_incoherente(fabrica_sesiones, reloj):
    with fabrica_sesiones() as s:
        carlos = crear_usuario(s, "Carlos")
        enzo = crear_usuario(s, "Enzo", rol=RolUsuario.COORDINADOR)
        ana, beto = crear_usuario(s, "Ana"), crear_usuario(s, "Beto")
        horario = crear_horario_de_prueba(s, carlos.id)
        turno_id = f"{horario.id}:{FECHA}"
        generar_vacante(s, turno_id, carlos, None, reloj, ZONA)
        s.commit()
        enzo_id, ana_id, beto_id = enzo.id, ana.id, beto.id

    with fabrica_sesiones() as s1, fabrica_sesiones() as s2:
        asignar(s1, turno_id, ana_id, False, s1.get(Usuario, enzo_id), reloj, ZONA)
        resultado = bloqueado_hasta_commit(s1, lambda: postular(s2, turno_id, s2.get(Usuario, beto_id), reloj, ZONA))

    # Al despertar, la vacante ya está cubierta: la postulación se rechaza en lugar de quedar a medias.
    assert isinstance(resultado.get("error"), ErrorDominio)
    assert resultado["error"].codigo == "TURNO_SIN_VACANTE"
    with fabrica_sesiones() as s:
        assert s.scalar(select(func.count()).select_from(Postulacion)) == 0
        assert s.scalar(select(Vacante.estado)) == EstadoVacante.CUBIERTA

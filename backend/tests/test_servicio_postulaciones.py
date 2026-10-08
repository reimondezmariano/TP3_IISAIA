from datetime import date, time, timedelta

import pytest
from sqlalchemy import func, select

from app.errores import ErrorDominio
from app.modelos import EstadoUsuario, EventoTurno, Postulacion, RolUsuario, TipoEventoTurno, Turno
from app.servicios.postulaciones import postular, retirar_postulacion
from app.servicios.sin_cobertura import marcar_sin_cobertura
from app.servicios.vacantes import generar_vacante
from fabricas import ZONA, bloqueado_hasta_commit, crear_horario_de_prueba, crear_usuario, guardar_turno

# Reloj de prueba: lunes 12/10/2026 09:00. El turno de prueba es el martes 20/10 (08:00 a 20:00).
FECHA = "2026-10-20"


def escena(sesion, reloj, con_vacante=True):
    carlos = crear_usuario(sesion, "Carlos")
    mariano = crear_usuario(sesion, "Mariano")
    horario = crear_horario_de_prueba(sesion, carlos.id)
    turno_id = f"{horario.id}:{FECHA}"
    if con_vacante:
        generar_vacante(sesion, turno_id, carlos, "Congreso", reloj, ZONA)
    return carlos, mariano, horario, turno_id


def pedir(sesion, reloj, turno_id, actor):
    return postular(sesion, turno_id, actor, reloj, ZONA)


def eventos(sesion, tipo):
    return list(sesion.scalars(select(EventoTurno).where(EventoTurno.tipo == tipo).order_by(EventoTurno.id)))


def error_de(sesion, reloj, turno_id, actor):
    with pytest.raises(ErrorDominio) as error:
        pedir(sesion, reloj, turno_id, actor)
    return error.value


def test_un_medico_se_postula_a_un_turno_con_vacante(sesion, reloj):
    _, mariano, _, turno_id = escena(sesion, reloj)

    postulacion = pedir(sesion, reloj, turno_id, mariano)

    assert (postulacion.medico_id, postulacion.creada_en, postulacion.retirada_en) == (mariano.id, reloj.ahora(), None)
    assert sesion.get(Turno, postulacion.turno_id).fecha == date(2026, 10, 20)


def test_postularse_deja_el_evento(sesion, reloj):
    _, mariano, _, turno_id = escena(sesion, reloj)
    postulacion = pedir(sesion, reloj, turno_id, mariano)
    [evento] = eventos(sesion, TipoEventoTurno.POSTULACION_CREADA)
    assert (evento.actor_id, evento.ocurrido_en, evento.turno_id) == (mariano.id, reloj.ahora(), postulacion.turno_id)
    assert evento.datos == {"postulacion_id": postulacion.id, "medico_id": mariano.id, "reactivada": False}


def test_el_titular_no_se_postula_a_su_propio_turno(sesion, reloj):
    carlos, _, _, turno_id = escena(sesion, reloj)
    error = error_de(sesion, reloj, turno_id, carlos)
    assert (error.codigo, error.status) == ("ES_TITULAR", 422)


def test_no_se_postula_con_una_guardia_superpuesta(sesion, reloj):
    _, mariano, _, turno_id = escena(sesion, reloj)
    crear_horario_de_prueba(sesion, mariano.id, hora=time(10), dur=6)  # su propio martes 10:00 a 16:00
    error = error_de(sesion, reloj, turno_id, mariano)
    assert (error.codigo, error.status) == ("GUARDIA_SUPERPUESTA", 422)


def test_una_guardia_que_termina_cuando_empieza_el_turno_no_impide(sesion, reloj):
    _, mariano, _, turno_id = escena(sesion, reloj)
    crear_horario_de_prueba(sesion, mariano.id, hora=time(2), dur=6)  # martes 02:00 a 08:00
    assert pedir(sesion, reloj, turno_id, mariano).retirada_en is None


@pytest.mark.parametrize(
    ("rol", "estado"),
    [(RolUsuario.COORDINADOR, EstadoUsuario.ACTIVO), (RolUsuario.MEDICO, EstadoUsuario.PENDIENTE)],
)
def test_coordinadores_y_pendientes_no_se_postulan(sesion, reloj, rol, estado):
    _, _, _, turno_id = escena(sesion, reloj)
    intruso = crear_usuario(sesion, "Intruso", rol=rol, estado=estado)
    error = error_de(sesion, reloj, turno_id, intruso)
    assert (error.codigo, error.status) == ("NO_HABILITADO", 403)


def test_baja_con_fecha_futura_se_postula_hasta_su_ultimo_dia_y_no_despues(sesion, reloj):
    _, _, _, turno_id = escena(sesion, reloj)
    hasta_el_turno = crear_usuario(sesion, "Baja el 20", estado=EstadoUsuario.BAJA, fecha_baja=date(2026, 10, 20))
    antes_del_turno = crear_usuario(sesion, "Baja el 19", estado=EstadoUsuario.BAJA, fecha_baja=date(2026, 10, 19))

    assert pedir(sesion, reloj, turno_id, hasta_el_turno).medico_id == hasta_el_turno.id
    assert error_de(sesion, reloj, turno_id, antes_del_turno).codigo == "NO_HABILITADO"


def test_turno_sin_vacante_responde_409(sesion, reloj):
    _, mariano, _, turno_id = escena(sesion, reloj, con_vacante=False)
    error = error_de(sesion, reloj, turno_id, mariano)
    assert (error.codigo, error.status) == ("TURNO_SIN_VACANTE", 409)


def test_turno_sin_titular_admite_postulacion_sin_vacante(sesion, reloj):
    mariano = crear_usuario(sesion, "Mariano")
    horario = crear_horario_de_prueba(sesion, None)

    postulacion = pedir(sesion, reloj, f"{horario.id}:{FECHA}", mariano)  # D24: se cubre por el circuito habitual

    assert sesion.get(Turno, postulacion.turno_id).titular_id is None


def test_un_turno_marcado_sin_cobertura_ya_empezo_y_no_admite_postulaciones(sesion, reloj):
    # D19: solo se marca sin cobertura un turno que ya empezó, y a esos solo se los asigna (hasta su fin).
    carlos, mariano, _, turno_id = escena(sesion, reloj)
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    reloj.avanzar(timedelta(days=8, hours=1))  # martes 20/10 10:00
    marcar_sin_cobertura(sesion, turno_id, enzo, reloj, ZONA)

    error = error_de(sesion, reloj, turno_id, mariano)

    assert (error.codigo, error.status) == ("TURNO_YA_EMPEZO", 409)


def test_el_asignado_no_se_postula_a_su_propio_turno(sesion, reloj):
    mariano = crear_usuario(sesion, "Mariano")
    horario = crear_horario_de_prueba(sesion, None)
    guardar_turno(sesion, horario.id, date(2026, 10, 20), asignado_id=mariano.id)
    error = error_de(sesion, reloj, f"{horario.id}:{FECHA}", mariano)
    assert (error.codigo, error.status) == ("YA_ASIGNADO", 409)


def test_postularse_dos_veces_responde_409(sesion, reloj):
    _, mariano, _, turno_id = escena(sesion, reloj)
    pedir(sesion, reloj, turno_id, mariano)
    error = error_de(sesion, reloj, turno_id, mariano)
    assert (error.codigo, error.status) == ("YA_POSTULADO", 409)


def test_turno_empezado_responde_409(sesion, reloj):
    _, mariano, _, turno_id = escena(sesion, reloj)
    reloj.avanzar(timedelta(days=8))  # martes 20/10 09:00: el turno de las 08:00 ya empezó
    error = error_de(sesion, reloj, turno_id, mariano)
    assert (error.codigo, error.status) == ("TURNO_YA_EMPEZO", 409)


def test_turno_inexistente_responde_404(sesion, reloj):
    _, mariano, horario, _ = escena(sesion, reloj)
    error = error_de(sesion, reloj, f"{horario.id}:2026-10-21", mariano)  # miércoles
    assert error.codigo == "TURNO_NO_ENCONTRADO"


def test_repostularse_reactiva_la_misma_fila_con_nueva_hora(sesion, reloj):
    _, mariano, _, turno_id = escena(sesion, reloj)
    primera = pedir(sesion, reloj, turno_id, mariano)
    reloj.avanzar(timedelta(hours=1))
    retirar_postulacion(sesion, primera.id, mariano, reloj)
    reloj.avanzar(timedelta(hours=1))

    segunda = pedir(sesion, reloj, turno_id, mariano)

    assert segunda.id == primera.id and segunda.retirada_en is None and segunda.creada_en == reloj.ahora()
    assert sesion.scalar(select(func.count()).select_from(Postulacion)) == 1
    assert eventos(sesion, TipoEventoTurno.POSTULACION_CREADA)[-1].datos["reactivada"] is True


# --- retiro ---


def test_retiro_por_el_dueno_deja_el_evento(sesion, reloj):
    _, mariano, _, turno_id = escena(sesion, reloj)
    postulacion = pedir(sesion, reloj, turno_id, mariano)
    reloj.avanzar(timedelta(hours=2))

    retirada = retirar_postulacion(sesion, postulacion.id, mariano, reloj)

    assert retirada.retirada_en == reloj.ahora()
    [evento] = eventos(sesion, TipoEventoTurno.POSTULACION_RETIRADA)
    assert (evento.actor_id, evento.datos) == (mariano.id, {"postulacion_id": postulacion.id, "medico_id": mariano.id})


def test_retiro_por_un_coordinador(sesion, reloj):
    _, mariano, _, turno_id = escena(sesion, reloj)
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    postulacion = pedir(sesion, reloj, turno_id, mariano)
    assert retirar_postulacion(sesion, postulacion.id, enzo, reloj).retirada_en == reloj.ahora()


def test_un_tercero_no_retira(sesion, reloj):
    _, mariano, _, turno_id = escena(sesion, reloj)
    postulacion = pedir(sesion, reloj, turno_id, mariano)
    with pytest.raises(ErrorDominio) as error:
        retirar_postulacion(sesion, postulacion.id, crear_usuario(sesion, "Tercero"), reloj)
    assert (error.value.codigo, error.value.status) == ("SIN_PERMISO", 403)


def test_retiro_de_una_postulacion_ya_retirada_o_inexistente(sesion, reloj):
    _, mariano, _, turno_id = escena(sesion, reloj)
    postulacion = pedir(sesion, reloj, turno_id, mariano)
    retirar_postulacion(sesion, postulacion.id, mariano, reloj)
    with pytest.raises(ErrorDominio) as ya:
        retirar_postulacion(sesion, postulacion.id, mariano, reloj)
    with pytest.raises(ErrorDominio) as no_existe:
        retirar_postulacion(sesion, 99999, mariano, reloj)
    assert (ya.value.codigo, ya.value.status) == ("POSTULACION_YA_RETIRADA", 409)
    assert (no_existe.value.codigo, no_existe.value.status) == ("POSTULACION_NO_ENCONTRADA", 404)


@pytest.mark.commit_real
def test_dos_postulaciones_simultaneas_del_mismo_medico_dejan_una_fila(fabrica_sesiones, reloj):
    with fabrica_sesiones() as s:
        _, mariano, _, turno_id = escena(s, reloj)
        s.commit()
        mariano_id, tipo = mariano.id, type(mariano)

    with fabrica_sesiones() as s1, fabrica_sesiones() as s2:
        pedir(s1, reloj, turno_id, s1.get(tipo, mariano_id))
        resultado = bloqueado_hasta_commit(s1, lambda: pedir(s2, reloj, turno_id, s2.get(tipo, mariano_id)))

    assert isinstance(resultado.get("error"), ErrorDominio)
    assert resultado["error"].codigo == "YA_POSTULADO"
    with fabrica_sesiones() as s:
        assert s.scalar(select(func.count()).select_from(Postulacion)) == 1

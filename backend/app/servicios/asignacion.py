"""Asignación de un turno (D17, D18, D19, D31). No hace commit; lo hace el router."""

from dataclasses import dataclass
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dominio.asignacion import CasoAsignacion, clasificar_asignacion, habilitado_para_turno
from app.dominio.elegibilidad import motivo_inelegibilidad
from app.dominio.notificaciones import TipoNotificacion
from app.errores import ErrorDominio
from app.modelos import EstadoVacante, EventoTurno, RolUsuario, TipoEventoTurno, Turno, Usuario, Vacante
from app.reloj import Reloj
from app.repos.guardias import guardias_del_medico
from app.repos.turnos import materializar_turno
from app.repos.usuarios import bloquear_usuario
from app.servicios.notificaciones import notificar
from app.servicios.postulaciones import MENSAJE_MOTIVO, listar_candidatos

_EVENTO = {
    CasoAsignacion.CANDIDATO_ELEGIDO: TipoEventoTurno.CANDIDATO_ELEGIDO,
    CasoAsignacion.ASIGNACION_DIRECTA: TipoEventoTurno.ASIGNACION_DIRECTA,
    CasoAsignacion.REASIGNACION: TipoEventoTurno.REASIGNACION,
}


@dataclass(frozen=True)
class ResultadoAsignacion:
    turno: Turno
    asignado: Usuario
    caso: CasoAsignacion
    vacante: Vacante | None  # la vacante que se cerró, si había


def asignar(
    sesion: Session, turno_id: str, medico_id: int, reasignar: bool, actor: Usuario, reloj: Reloj, zona: ZoneInfo
) -> ResultadoAsignacion:
    """"Esta persona cubre este turno" (D18): elección de un candidato, asignación directa o reasignación.

    Solo coordinadores, hasta el fin del turno (D19). El coordinador puede elegir a cualquier candidato, no solo
    al primero (D17), pero no a quien no está habilitado para ese turno ni tiene una guardia superpuesta (D16).
    Si el turno ya tiene asignado hace falta `reasignar`, así dos coordinadores no se pisan. Cierra la vacante
    abierta como CUBIERTA y, si el turno estaba marcado sin cobertura, levanta la marca en la misma transacción.
    Orden de bloqueos (convención 19): primero el médico elegido, después el turno y su vacante.
    """
    if actor.rol != RolUsuario.COORDINADOR:
        raise ErrorDominio("SIN_PERMISO", "Solo un coordinador puede asignar un turno.", 403)
    ahora = reloj.ahora()
    medico = bloquear_usuario(sesion, medico_id)
    if medico is None:
        raise ErrorDominio("USUARIO_NO_ENCONTRADO", "No existe ese usuario.", 404)
    turno = materializar_turno(sesion, turno_id, zona)
    if turno.consolidado_en is not None or ahora >= turno.fin:
        raise ErrorDominio("TURNO_TERMINADO", "El turno ya terminó: no se puede asignar.", 409)
    if not habilitado_para_turno(medico.rol, medico.estado, medico.fecha_baja, turno.fecha):
        raise ErrorDominio("NO_HABILITADO", "Esa persona no puede cubrir este turno.", 422)
    if medico.id == turno.titular_id:
        raise ErrorDominio("ES_TITULAR", "El titular no puede cubrir su propio turno.", 422)
    if medico.id == turno.asignado_id:
        raise ErrorDominio("YA_ASIGNADO", "Esa persona ya tiene asignado este turno.", 409)
    if turno.asignado_id is not None and not reasignar:
        raise ErrorDominio("YA_TIENE_ASIGNADO", "El turno ya tiene asignado: para cambiarlo hay que reasignar.", 409)

    abierta = sesion.scalar(
        select(Vacante)
        .where(Vacante.turno_id == turno.id, Vacante.estado == EstadoVacante.ABIERTA)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    sin_cobertura = turno.sin_cobertura_en is not None
    if abierta is None and turno.asignado_id is None and turno.titular_id is not None and not sin_cobertura:
        raise ErrorDominio("TURNO_SIN_VACANTE", "El turno no tiene una vacante abierta.", 409)

    guardias = guardias_del_medico(sesion, medico.id, turno.inicio, turno.fin, turno_id, zona)
    motivo = motivo_inelegibilidad(medico.id, turno.titular_id, turno.inicio, turno.fin, guardias)
    if motivo is not None:
        raise ErrorDominio(motivo.value, MENSAJE_MOTIVO[motivo], 422)

    candidatos = listar_candidatos(sesion, turno_id, zona).candidatos
    candidato = next((c for c in candidatos if c.medico.id == medico.id), None)
    caso = clasificar_asignacion(turno.asignado_id is not None, candidato is not None)

    anterior = turno.asignado_id
    turno.asignado_id = medico.id
    cerrada = abierta
    if abierta is not None:
        abierta.estado = EstadoVacante.CUBIERTA
        abierta.cerrada_en = ahora
    if sin_cobertura:
        turno.sin_cobertura_en = None
        cerrada = cerrada or sesion.scalar(
            select(Vacante)
            .where(Vacante.turno_id == turno.id, Vacante.estado == EstadoVacante.SIN_COBERTURA)
            .order_by(Vacante.id.desc())
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if cerrada is not None and cerrada.estado == EstadoVacante.SIN_COBERTURA:
            cerrada.estado = EstadoVacante.CUBIERTA
            cerrada.cerrada_en = ahora

    datos: dict = {"asignado_id": medico.id}
    if caso is CasoAsignacion.CANDIDATO_ELEGIDO:
        datos |= {"posicion": candidato.posicion, "candidatos": len(candidatos)}
    if caso is CasoAsignacion.REASIGNACION:
        datos["asignado_anterior_id"] = anterior
    if sin_cobertura:
        datos["sin_cobertura_levantada"] = True
    sesion.add(
        EventoTurno(turno_id=turno.id, tipo=_EVENTO[caso], actor_id=actor.id, ocurrido_en=ahora, datos=datos)
    )
    sesion.flush()

    inicio = turno.inicio.astimezone(zona)
    notificar(
        sesion,
        [medico.id],
        TipoNotificacion.TURNO_ASIGNADO,
        f"Te asignaron la guardia del {inicio:%d/%m} a las {inicio:%H:%M}.",
        ahora,
        turno=turno,
        datos={"turnoId": turno_id, "caso": caso.value},
    )
    return ResultadoAsignacion(turno, medico, caso, cerrada)

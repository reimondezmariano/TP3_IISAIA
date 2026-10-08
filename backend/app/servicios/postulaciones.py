"""Postulaciones al turno y candidatos (D16, D17). No hacen commit; lo hace el router."""

from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dominio.asignacion import habilitado_para_turno
from app.dominio.elegibilidad import Motivo, motivo_inelegibilidad
from app.errores import ErrorDominio
from app.modelos import EstadoVacante, EventoTurno, Postulacion, RolUsuario, TipoEventoTurno, Turno, Usuario, Vacante
from app.reloj import Reloj
from app.repos.guardias import guardias_del_medico
from app.repos.turnos import materializar_turno

_MENSAJE_MOTIVO = {
    Motivo.ES_TITULAR: "Sos el titular de este turno: no podés postularte.",
    Motivo.GUARDIA_SUPERPUESTA: "Tenés otra guardia que se superpone con este turno.",
}


def tiene_vacante_abierta(sesion: Session, turno: Turno) -> bool:
    return (
        sesion.scalar(
            select(Vacante.id).where(Vacante.turno_id == turno.id, Vacante.estado == EstadoVacante.ABIERTA)
        )
        is not None
    )


def postular(sesion: Session, turno_id: str, actor: Usuario, reloj: Reloj, zona: ZoneInfo) -> Postulacion:
    """Oferta del médico para cubrir el turno "horarioId:fecha" (D16).

    Vale hasta que el turno empiece o el médico la retire, y sobrevive a la asignación: es la reserva para una
    cancelación. Se postula a un turno con vacante abierta, sin titular (D24) o marcado sin cobertura (D19).
    Una postulación retirada se reactiva: la fila es única por (turno, médico) y vuelve al final del desempate.
    """
    ahora = reloj.ahora()
    turno = materializar_turno(sesion, turno_id, zona)
    if not habilitado_para_turno(actor.rol, actor.estado, actor.fecha_baja, turno.fecha):
        raise ErrorDominio("NO_HABILITADO", "Solo un médico con acceso ese día puede postularse a este turno.", 403)
    if turno.consolidado_en is not None or ahora >= turno.inicio:
        raise ErrorDominio("TURNO_YA_EMPEZO", "El turno ya empezó: no se puede postular.", 409)
    if not (tiene_vacante_abierta(sesion, turno) or turno.titular_id is None or turno.sin_cobertura_en is not None):
        raise ErrorDominio("TURNO_SIN_VACANTE", "El turno no tiene una vacante abierta.", 409)
    if turno.asignado_id == actor.id:
        raise ErrorDominio("YA_ASIGNADO", "Ya tenés asignado este turno.", 409)

    existente = sesion.scalar(
        select(Postulacion).where(Postulacion.turno_id == turno.id, Postulacion.medico_id == actor.id)
    )
    if existente is not None and existente.retirada_en is None:
        raise ErrorDominio("YA_POSTULADO", "Ya estás postulado a este turno.", 409)

    guardias = guardias_del_medico(sesion, actor.id, turno.inicio, turno.fin, turno_id, zona)
    motivo = motivo_inelegibilidad(actor.id, turno.titular_id, turno.inicio, turno.fin, guardias)
    if motivo is not None:
        raise ErrorDominio(motivo.value, _MENSAJE_MOTIVO[motivo], 422)

    reactivada = existente is not None
    if reactivada:
        postulacion = existente
        postulacion.retirada_en = None
        postulacion.creada_en = ahora
    else:
        postulacion = Postulacion(turno_id=turno.id, medico_id=actor.id, creada_en=ahora)
        sesion.add(postulacion)
    sesion.flush()
    sesion.add(
        EventoTurno(
            turno_id=turno.id,
            tipo=TipoEventoTurno.POSTULACION_CREADA,
            actor_id=actor.id,
            ocurrido_en=ahora,
            datos={"postulacion_id": postulacion.id, "medico_id": actor.id, "reactivada": reactivada},
        )
    )
    sesion.flush()
    return postulacion


def retirar_postulacion(sesion: Session, postulacion_id: int, actor: Usuario, reloj: Reloj) -> Postulacion:
    """Retira la postulación: su dueño o un coordinador (D16). No toca la asignación."""
    postulacion = sesion.get(Postulacion, postulacion_id)
    if postulacion is None:
        raise ErrorDominio("POSTULACION_NO_ENCONTRADA", "No existe esa postulación.", 404)
    sesion.scalar(  # con el turno bloqueado, el estado es el que dejó la última transacción
        select(Turno.id).where(Turno.id == postulacion.turno_id).with_for_update()
    )
    sesion.refresh(postulacion)
    if actor.id != postulacion.medico_id and actor.rol != RolUsuario.COORDINADOR:
        raise ErrorDominio("SIN_PERMISO", "Solo quien se postuló o un coordinador pueden retirarla.", 403)
    if postulacion.retirada_en is not None:
        raise ErrorDominio("POSTULACION_YA_RETIRADA", "La postulación ya estaba retirada.", 409)
    ahora = reloj.ahora()
    postulacion.retirada_en = ahora
    sesion.add(
        EventoTurno(
            turno_id=postulacion.turno_id,
            tipo=TipoEventoTurno.POSTULACION_RETIRADA,
            actor_id=actor.id,
            ocurrido_en=ahora,
            datos={"postulacion_id": postulacion.id, "medico_id": postulacion.medico_id},
        )
    )
    sesion.flush()
    return postulacion

"""Operaciones sobre vacantes (D15, D31). No hacen commit; lo hace el router."""

from dataclasses import dataclass
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dominio.vacantes import es_urgente, puede_generar
from app.errores import ErrorDominio
from app.modelos import (
    EstadoUsuario,
    EstadoVacante,
    EventoTurno,
    Notificacion,
    RolUsuario,
    TipoEventoTurno,
    Turno,
    Usuario,
    Vacante,
)
from app.reloj import Reloj
from app.repos.turnos import materializar_turno


@dataclass(frozen=True)
class ResultadoVacante:
    vacante: Vacante
    turno: Turno
    urgente: bool
    asignado_anterior_id: int | None


def generar_vacante(
    sesion: Session, turno_id: str, actor: Usuario, motivo: str | None, reloj: Reloj, zona: ZoneInfo
) -> ResultadoVacante:
    """Abre una vacante sobre el turno "horarioId:fecha" (D15).

    La generan el titular, el asignado vigente o un coordinador, hasta el inicio del turno. Si el turno tenía
    un asignado se borra en esta misma transacción y queda en el evento VACANTE_GENERADA (D31, D08 punto 4).
    Una vacante urgente (menos de 24 h) avisa a los médicos activos (D05). El turno queda bloqueado hasta el
    commit, así que dos pedidos simultáneos no abren dos vacantes.
    """
    ahora = reloj.ahora()
    turno = materializar_turno(sesion, turno_id, zona)
    if not puede_generar(actor.id, actor.rol == RolUsuario.COORDINADOR, turno.titular_id, turno.asignado_id):
        raise ErrorDominio("SIN_PERMISO", "Solo el titular, el asignado o un coordinador pueden generar la vacante.", 403)
    if turno.consolidado_en is not None or ahora >= turno.inicio:
        raise ErrorDominio("TURNO_YA_EMPEZO", "El turno ya empezó: no se puede generar una vacante.", 409)
    abierta = sesion.scalar(
        select(Vacante.id).where(Vacante.turno_id == turno.id, Vacante.estado == EstadoVacante.ABIERTA)
    )
    if abierta is not None:
        raise ErrorDominio("VACANTE_YA_ABIERTA", "El turno ya tiene una vacante abierta.", 409)

    urgente = es_urgente(turno.inicio, ahora)
    asignado_anterior_id = turno.asignado_id
    vacante = Vacante(turno_id=turno.id, generada_por_id=actor.id, motivo=motivo, creada_en=ahora)
    sesion.add(vacante)
    sesion.flush()
    turno.asignado_id = None  # D31: turno con vacante abierta es turno sin asignado
    sesion.add(
        EventoTurno(
            turno_id=turno.id,
            tipo=TipoEventoTurno.VACANTE_GENERADA,
            actor_id=actor.id,
            ocurrido_en=ahora,
            datos={"urgente": urgente, "asignado_anterior_id": asignado_anterior_id, "vacante_id": vacante.id},
        )
    )
    sesion.flush()
    if urgente:
        _avisar_urgencia(sesion, turno, vacante, turno_id, actor, zona, ahora)
    return ResultadoVacante(vacante, turno, urgente, asignado_anterior_id)


def _avisar_urgencia(sesion, turno: Turno, vacante: Vacante, turno_id: str, actor: Usuario, zona, ahora) -> None:
    medicos = sesion.scalars(
        select(Usuario)
        .where(Usuario.rol == RolUsuario.MEDICO, Usuario.estado == EstadoUsuario.ACTIVO, Usuario.id != actor.id)
        .order_by(Usuario.id)
    )
    inicio = turno.inicio.astimezone(zona)
    for medico in medicos:
        sesion.add(
            Notificacion(
                usuario_id=medico.id,
                tipo="VACANTE_URGENTE",
                mensaje=f"Vacante urgente: guardia del {inicio:%d/%m} a las {inicio:%H:%M}.",
                turno_id=turno.id,
                datos={"turnoId": turno_id, "vacanteId": vacante.id},
                creada_en=ahora,
            )
        )
    sesion.flush()

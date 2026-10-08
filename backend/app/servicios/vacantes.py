"""Operaciones sobre vacantes (D15, D31). No hacen commit; lo hace el router."""

from collections.abc import Sequence
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dominio.calendario import parsear_id_turno
from app.dominio.notificaciones import TipoNotificacion
from app.dominio.vacantes import asignado_a_restaurar, es_urgente, puede_generar, puede_retirar
from app.errores import ErrorDominio
from app.modelos import (
    EstadoVacante,
    EventoTurno,
    RolUsuario,
    TipoEventoTurno,
    Turno,
    Usuario,
    Vacante,
)
from app.reloj import Reloj
from app.repos.turnos import bloquear_turnos, materializar_turno
from app.servicios.notificaciones import destinatarios, notificar


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
    Una vacante urgente (menos de 24 h) avisa a los médicos activos (D05); una que no es urgente también, con
    VACANTE_ABIERTA (solo campanita). El turno queda bloqueado hasta el
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
    else:
        _avisar_vacante(sesion, turno, vacante, turno_id, actor, zona, ahora)
    return ResultadoVacante(vacante, turno, urgente, asignado_anterior_id)


def _avisar_urgencia(sesion: Session, turno: Turno, vacante: Vacante, turno_id: str, actor: Usuario, zona, ahora) -> None:
    """Aviso a los médicos con acceso hoy, salvo quien generó la vacante (D05, D24). Usa `notificar` de F4."""
    inicio = turno.inicio.astimezone(zona)
    notificar(
        sesion,
        destinatarios(sesion, RolUsuario.MEDICO, ahora.astimezone(zona).date(), excepto=[actor.id]),
        TipoNotificacion.VACANTE_URGENTE,
        f"Vacante urgente: guardia del {inicio:%d/%m} a las {inicio:%H:%M}.",
        ahora,
        turno=turno,
        datos={"turnoId": turno_id, "vacanteId": vacante.id},
    )


def _avisar_vacante(sesion: Session, turno: Turno, vacante: Vacante, turno_id: str, actor: Usuario, zona, ahora) -> None:
    """Vacante que no es urgente: a la campanita de los mismos destinatarios que la urgente, sin aviso emergente."""
    inicio = turno.inicio.astimezone(zona)
    notificar(
        sesion,
        destinatarios(sesion, RolUsuario.MEDICO, ahora.astimezone(zona).date(), excepto=[actor.id]),
        TipoNotificacion.VACANTE_ABIERTA,
        f"Vacante: guardia del {inicio:%d/%m} a las {inicio:%H:%M}.",
        ahora,
        turno=turno,
        datos={"turnoId": turno_id, "vacanteId": vacante.id},
    )


def generar_lote(
    sesion: Session,
    turno_ids: Sequence[str],
    actor: Usuario,
    motivo: str | None,
    reloj: Reloj,
    zona: ZoneInfo,
) -> list[ResultadoVacante]:
    """Una vacante por turno, todo o nada (D15). Devuelve los resultados en el orden pedido.

    Bloquea todos los turnos por (horario, fecha) ascendente antes de generar, así que dos lotes cruzados no
    se traban. Si uno falla, el error indica qué turno y se deshacen todos los anteriores.
    """
    if len(set(turno_ids)) != len(turno_ids):
        raise ErrorDominio("TURNOS_REPETIDOS", "El lote repite turnos.")
    for turno_id in turno_ids:
        parsear_id_turno(turno_id)
    with sesion.begin_nested():
        bloquear_turnos(sesion, turno_ids, zona)
        resultados: list[ResultadoVacante] = []
        for turno_id in sorted(turno_ids, key=parsear_id_turno):
            try:
                resultados.append(generar_vacante(sesion, turno_id, actor, motivo, reloj, zona))
            except ErrorDominio as error:
                raise ErrorDominio(error.codigo, f"{turno_id}: {error.mensaje}", error.status) from error
    por_turno = {f"{r.turno.horario_id}:{r.turno.fecha.isoformat()}": r for r in resultados}
    return [por_turno[turno_id] for turno_id in turno_ids]


def retirar_vacante(sesion: Session, vacante_id: int, actor: Usuario, reloj: Reloj) -> Vacante:
    """Retira una vacante abierta: quien la generó o un coordinador (D15).

    Si la había generado el asignado que se borró al abrirla, el retiro lo restaura (D31, supuesto 3 del plan).
    """
    vacante = sesion.get(Vacante, vacante_id)
    if vacante is None:
        raise ErrorDominio("VACANTE_NO_ENCONTRADA", "No existe esa vacante.", 404)
    turno = sesion.scalar(
        select(Turno).where(Turno.id == vacante.turno_id).with_for_update().execution_options(populate_existing=True)
    )
    sesion.refresh(vacante)  # con el turno bloqueado, el estado es el que dejó la última transacción
    if not puede_retirar(actor.id, actor.rol == RolUsuario.COORDINADOR, vacante.generada_por_id):
        raise ErrorDominio("SIN_PERMISO", "Solo quien generó la vacante o un coordinador pueden retirarla.", 403)
    if vacante.estado != EstadoVacante.ABIERTA:
        raise ErrorDominio("VACANTE_NO_ABIERTA", "La vacante ya no está abierta.", 409)

    ahora = reloj.ahora()
    generada = sesion.scalar(
        select(EventoTurno).where(
            EventoTurno.turno_id == turno.id,
            EventoTurno.tipo == TipoEventoTurno.VACANTE_GENERADA,
            EventoTurno.datos["vacante_id"].astext == str(vacante.id),
        )
    )
    anterior = generada.datos.get("asignado_anterior_id") if generada is not None else None
    restaurado = asignado_a_restaurar(vacante.generada_por_id, anterior)
    vacante.estado = EstadoVacante.RETIRADA
    vacante.cerrada_en = ahora
    if restaurado is not None and turno.asignado_id is None:
        turno.asignado_id = restaurado
    sesion.add(
        EventoTurno(
            turno_id=turno.id,
            tipo=TipoEventoTurno.VACANTE_RETIRADA,
            actor_id=actor.id,
            ocurrido_en=ahora,
            datos={"vacante_id": vacante.id, "asignado_restaurado_id": restaurado},
        )
    )
    sesion.flush()
    return vacante

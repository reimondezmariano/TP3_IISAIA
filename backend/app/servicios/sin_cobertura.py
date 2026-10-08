"""Turno sin cobertura (D19): el coordinador lo marca cuando la vacante sigue abierta al llegar el inicio."""

from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dominio.calendario import calcular_turnos, parsear_id_turno
from app.errores import ErrorDominio
from app.modelos import EstadoVacante, EventoTurno, TipoEventoTurno, Turno, Usuario, Vacante
from app.reloj import Reloj
from app.repos.horarios import versiones_en_rango


def marcar_sin_cobertura(
    sesion: Session, turno_id: str, actor: Usuario, reloj: Reloj, zona: ZoneInfo
) -> tuple[Turno, Vacante]:
    """Cierra la vacante como SIN_COBERTURA y lo registra en la bitácora (D19, D22). No hace commit."""
    horario_id, fecha = parsear_id_turno(turno_id)
    turno = sesion.scalar(
        select(Turno)
        .where(Turno.horario_id == horario_id, Turno.fecha == fecha)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if turno is None:
        # Sin fila no hay vacante (D11); solo falta distinguir un turno inexistente.
        calculados = calcular_turnos(versiones_en_rango(sesion, fecha, fecha), fecha, fecha, zona)
        if not any(t.horario_id == horario_id and t.fecha == fecha for t in calculados):
            raise ErrorDominio("TURNO_NO_ENCONTRADO", f"No existe el turno {turno_id}.", 404)
        raise ErrorDominio("TURNO_SIN_VACANTE", "El turno no tiene una vacante abierta.", 409)
    if turno.consolidado_en is not None:
        raise ErrorDominio("TURNO_CONSOLIDADO", "El turno ya terminó y se consolidó.", 409)
    if turno.sin_cobertura_en is not None:
        raise ErrorDominio("YA_SIN_COBERTURA", "El turno ya está marcado sin cobertura.", 409)
    vacante = sesion.scalar(
        select(Vacante)
        .where(Vacante.turno_id == turno.id, Vacante.estado == EstadoVacante.ABIERTA)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if vacante is None:
        raise ErrorDominio("TURNO_SIN_VACANTE", "El turno no tiene una vacante abierta.", 409)
    ahora = reloj.ahora()
    if ahora < turno.inicio:
        raise ErrorDominio("TURNO_NO_EMPEZO", "Un turno se marca sin cobertura cuando ya empezó (D19).")
    vacante.estado = EstadoVacante.SIN_COBERTURA
    vacante.cerrada_en = ahora
    turno.sin_cobertura_en = ahora
    sesion.add(
        EventoTurno(
            turno_id=turno.id,
            tipo=TipoEventoTurno.TURNO_SIN_COBERTURA,
            actor_id=actor.id,
            ocurrido_en=ahora,
            datos={"vacante_id": vacante.id},
        )
    )
    sesion.flush()
    return turno, vacante

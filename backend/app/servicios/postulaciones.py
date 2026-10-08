"""Postulaciones al turno y candidatos (D16, D17). No hacen commit; lo hace el router."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dominio.asignacion import habilitado_para_turno
from app.dominio.calendario import calcular_turnos, parsear_id_turno
from app.dominio.elegibilidad import Motivo, motivo_inelegibilidad
from app.dominio.equidad import Candidato, contar_coberturas, horas_en_semana, ordenar_candidatos
from app.errores import ErrorDominio
from app.modelos import EstadoVacante, EventoTurno, Postulacion, RolUsuario, TipoEventoTurno, Turno, Usuario, Vacante
from app.reloj import Reloj
from app.repos.guardias import guardias_del_medico, turnos_del_mes
from app.repos.horarios import versiones_en_rango
from app.repos.turnos import fecha_fuera_de_rango, materializar_turno, no_existe

MENSAJE_MOTIVO = {
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
    cancelación. Se postula a un turno con vacante abierta o sin titular (D24). Un turno marcado sin cobertura
    (D19) ya empezó, así que no admite postulaciones: solo se lo asigna.
    Una postulación retirada se reactiva: la fila es única por (turno, médico) y vuelve al final del desempate.
    """
    ahora = reloj.ahora()
    turno = materializar_turno(sesion, turno_id, zona)
    if not habilitado_para_turno(actor.rol, actor.estado, actor.fecha_baja, turno.fecha):
        raise ErrorDominio("NO_HABILITADO", "Solo un médico con acceso ese día puede postularse a este turno.", 403)
    if turno.consolidado_en is not None or ahora >= turno.inicio:
        raise ErrorDominio("TURNO_YA_EMPEZO", "El turno ya empezó: no se puede postular.", 409)
    if not (tiene_vacante_abierta(sesion, turno) or turno.titular_id is None):
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
        raise ErrorDominio(motivo.value, MENSAJE_MOTIVO[motivo], 422)

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


@dataclass(frozen=True)
class CandidatoCalculado:
    posicion: int | None  # 1..n entre los elegibles; None si no es elegible
    medico: Usuario
    postulado_en: datetime
    coberturas_mes: int
    horas_semana: float  # horas de guardia que ya tiene esa semana, sin contar este turno (dato informativo, D17)
    elegible: bool
    motivo: Motivo | None


@dataclass(frozen=True)
class ResultadoCandidatos:
    turno_id: str
    mes: str  # "AAAA-MM" del inicio del turno en la zona del servicio
    candidatos: list[CandidatoCalculado]


def listar_candidatos(sesion: Session, turno_id: str, zona: ZoneInfo) -> ResultadoCandidatos:
    """Postulaciones activas ordenadas por equidad (D17): primero quien cubrió menos en el mes del turno.

    Desempata la hora de postulación. Los no elegibles (D16) van al final con su motivo: la elegibilidad se
    calcula en cada consulta, así que si el impedimento desaparece vuelven a ser elegibles. Quedan fuera quienes
    ya no están habilitados para ese turno (coordinadores, bajas anteriores a su fecha), el asignado actual (no se
    lo puede elegir) y quien generó la vacante abierta: cancelar es decir que no puede (D16). No guarda el turno.
    """
    horario_id, fecha = parsear_id_turno(turno_id)
    if fecha_fuera_de_rango(fecha):
        raise no_existe(turno_id)
    turno = sesion.scalar(select(Turno).where(Turno.horario_id == horario_id, Turno.fecha == fecha))
    if turno is None:
        calculado = next(
            (
                t
                for t in calcular_turnos(versiones_en_rango(sesion, fecha, fecha), fecha, fecha, zona)
                if t.horario_id == horario_id and t.fecha == fecha
            ),
            None,
        )
        if calculado is None:
            raise no_existe(turno_id)
        inicio = calculado.inicio.astimezone(zona)
        return ResultadoCandidatos(turno_id, f"{inicio:%Y-%m}", [])

    inicio_local = turno.inicio.astimezone(zona)
    mes = f"{inicio_local:%Y-%m}"
    filas = sesion.execute(
        select(Postulacion, Usuario)
        .join(Usuario, Usuario.id == Postulacion.medico_id)
        .where(Postulacion.turno_id == turno.id, Postulacion.retirada_en.is_(None))
    ).all()
    cancelo = sesion.scalar(
        select(Vacante.generada_por_id).where(Vacante.turno_id == turno.id, Vacante.estado == EstadoVacante.ABIERTA)
    )
    habilitados = [
        (p, u)
        for p, u in filas
        if habilitado_para_turno(u.rol, u.estado, u.fecha_baja, turno.fecha) and u.id not in (turno.asignado_id, cancelo)
    ]
    if not habilitados:
        return ResultadoCandidatos(turno_id, mes, [])

    anio, numero_mes = inicio_local.year, inicio_local.month
    por_medico = contar_coberturas(turnos_del_mes(sesion, anio, numero_mes, zona), anio, numero_mes, zona)
    lunes = fecha - timedelta(days=fecha.weekday())
    inicio_semana = datetime.combine(lunes, time(0), tzinfo=zona)
    fin_semana = datetime.combine(lunes + timedelta(days=7), time(0), tzinfo=zona)

    elegibles: list[Candidato] = []
    no_elegibles: list[Candidato] = []
    detalle: dict[int, tuple[Usuario, Motivo | None, float]] = {}
    for postulacion, medico in habilitados:
        guardias = guardias_del_medico(sesion, medico.id, turno.inicio, turno.fin, turno_id, zona)
        motivo = motivo_inelegibilidad(medico.id, turno.titular_id, turno.inicio, turno.fin, guardias)
        semana = guardias_del_medico(sesion, medico.id, inicio_semana, fin_semana, turno_id, zona)
        detalle[medico.id] = (medico, motivo, horas_en_semana(semana, fecha, zona))
        (elegibles if motivo is None else no_elegibles).append(Candidato(medico.id, postulacion.creada_en))

    candidatos: list[CandidatoCalculado] = []
    posicion = 0
    for grupo, es_elegible in ((elegibles, True), (no_elegibles, False)):
        for candidato in ordenar_candidatos(grupo, por_medico):
            medico, motivo, horas = detalle[candidato.medico_id]
            posicion += 1 if es_elegible else 0
            candidatos.append(
                CandidatoCalculado(
                    posicion if es_elegible else None,
                    medico,
                    candidato.postulado_en,
                    por_medico.get(medico.id, 0),
                    horas,
                    es_elegible,
                    motivo,
                )
            )
    return ResultadoCandidatos(turno_id, mes, candidatos)

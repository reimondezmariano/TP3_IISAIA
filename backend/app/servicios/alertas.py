"""Alertas escalonadas a coordinadores por vacantes sin cubrir (D19). No hace commit."""

from collections import defaultdict
from collections.abc import Collection
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select, text
from sqlalchemy.orm import Session

from app.dominio.alertas import Umbral, alertas_pendientes
from app.dominio.notificaciones import TipoNotificacion, mensaje_alerta
from app.modelos import EstadoVacante, EventoTurno, RolUsuario, TipoEventoTurno, Turno, Vacante
from app.reloj import Reloj, hoy
from app.servicios.notificaciones import destinatarios, notificar

ANTICIPACION_MAXIMA = timedelta(hours=48)

# D19, regla 8: el índice único ux_evento_alerta_por_umbral garantiza una alerta por turno y umbral aunque dos
# pedidos lleguen juntos; el segundo espera al primero y no inserta nada.
_REGISTRAR_ALERTA = text(
    """
    INSERT INTO evento_turno (turno_id, tipo, actor_id, ocurrido_en, datos)
    VALUES (:turno_id, 'ALERTA_SIN_COBERTURA', NULL, :ahora, jsonb_build_object('umbral', CAST(:umbral AS text)))
    ON CONFLICT (turno_id, (datos->>'umbral')) WHERE tipo = 'ALERTA_SIN_COBERTURA' DO NOTHING
    RETURNING id
    """
)


def emitir_alertas(sesion: Session, reloj: Reloj, zona: ZoneInfo) -> int:
    ahora = reloj.ahora()
    filas = sesion.execute(
        select(Turno, Vacante)
        .join(Vacante, and_(Vacante.turno_id == Turno.id, Vacante.estado == EstadoVacante.ABIERTA))
        .where(Turno.inicio <= ahora + ANTICIPACION_MAXIMA, Turno.fin > ahora, Turno.consolidado_en.is_(None))
        .order_by(Turno.inicio, Turno.id)
    ).all()
    if not filas:
        return 0
    enviadas = _enviadas(sesion, [turno.id for turno, _ in filas])
    coordinadores: list[int] | None = None
    notificados = 0
    for turno, vacante in filas:
        vencidos = alertas_pendientes(turno.inicio, turno.fin, vacante.creada_en, ahora, enviadas[turno.id])
        registrados = [umbral for umbral in vencidos if _registrar(sesion, turno.id, umbral, ahora)]
        if not registrados:
            continue
        if coordinadores is None:
            coordinadores = destinatarios(sesion, RolUsuario.COORDINADOR, hoy(reloj))
        # Decisión 6 del plan: si vencieron varios a la vez, se avisa solo el más reciente.
        umbral = registrados[-1]
        notificar(
            sesion,
            coordinadores,
            TipoNotificacion.ALERTA_SIN_COBERTURA,
            mensaje_alerta(umbral, turno.inicio.astimezone(zona)),
            ahora,
            turno=turno,
            datos={"umbral": umbral.value},
        )
        notificados += 1
    return notificados


def _enviadas(sesion: Session, turno_ids: Collection[int]) -> defaultdict[int, set[Umbral]]:
    resultado: defaultdict[int, set[Umbral]] = defaultdict(set)
    filas = sesion.execute(
        select(EventoTurno.turno_id, EventoTurno.datos["umbral"].astext).where(
            EventoTurno.turno_id.in_(turno_ids), EventoTurno.tipo == TipoEventoTurno.ALERTA_SIN_COBERTURA
        )
    )
    for turno_id, umbral in filas:
        resultado[turno_id].add(Umbral(umbral))
    return resultado


def _registrar(sesion: Session, turno_id: int, umbral: Umbral, ahora: datetime) -> bool:
    insertado = sesion.execute(_REGISTRAR_ALERTA, {"turno_id": turno_id, "ahora": ahora, "umbral": umbral.value})
    return insertado.first() is not None

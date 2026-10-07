import enum
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base


class TipoEventoTurno(str, enum.Enum):
    VACANTE_GENERADA = "VACANTE_GENERADA"
    VACANTE_RETIRADA = "VACANTE_RETIRADA"
    POSTULACION_CREADA = "POSTULACION_CREADA"
    POSTULACION_RETIRADA = "POSTULACION_RETIRADA"
    CANDIDATO_ELEGIDO = "CANDIDATO_ELEGIDO"
    ASIGNACION_DIRECTA = "ASIGNACION_DIRECTA"
    REASIGNACION = "REASIGNACION"
    TURNO_SIN_COBERTURA = "TURNO_SIN_COBERTURA"
    REALIZADOR_RECTIFICADO = "REALIZADOR_RECTIFICADO"
    ALERTA_SIN_COBERTURA = "ALERTA_SIN_COBERTURA"


class EventoTurno(Base):
    """Bitácora de acciones sobre un turno (D22). Solo se agrega: un trigger rechaza UPDATE y DELETE.

    Se escribe en la misma transacción que la acción. actor_id vacío = acción del sistema.
    datos guarda solo lo que ninguna entidad conserva: posición y cantidad de candidatos,
    valor anterior, motivo de la rectificación, umbral de la alerta ("48H", "24H" o "INICIO").
    """

    __tablename__ = "evento_turno"
    __table_args__ = (
        CheckConstraint(
            "tipo <> 'ALERTA_SIN_COBERTURA' OR coalesce(datos->>'umbral', '') IN ('48H', '24H', 'INICIO')",
            name="ck_evento_alerta_umbral",
        ),
        Index("ix_evento_turno_turno", "turno_id", "ocurrido_en"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    turno_id: Mapped[int] = mapped_column(ForeignKey("turno.id"))
    tipo: Mapped[TipoEventoTurno] = mapped_column(Enum(TipoEventoTurno, name="tipo_evento_turno"))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    ocurrido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    datos: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))


Index(
    "ux_evento_alerta_por_umbral",
    EventoTurno.turno_id,
    EventoTurno.datos["umbral"].astext,
    unique=True,
    postgresql_where=EventoTurno.tipo == TipoEventoTurno.ALERTA_SIN_COBERTURA,
)

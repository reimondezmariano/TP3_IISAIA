import enum
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base


class Turno(Base):
    """Guardia concreta, guardada solo cuando se genera una vacante o al consolidarse (D08, D09, D11).

    inicio, fin, version_id y titular_id son una foto del momento en que se guardó: no se recalculan
    si cambia la plantilla (D11, D12). asignado_id es el asignado actual; los anteriores quedan en la
    bitácora (D08). realizador_id solo existe en un turno consolidado (D20, D21).
    """

    __tablename__ = "turno"
    __table_args__ = (
        UniqueConstraint("horario_id", "fecha", name="ux_turno_horario_fecha"),
        ForeignKeyConstraint(
            ["version_id", "horario_id"],
            ["version_horario.id", "version_horario.horario_id"],
            name="fk_turno_version_del_horario",
        ),
        CheckConstraint("fin > inicio", name="ck_turno_fin_posterior"),
        CheckConstraint(
            "realizador_id IS NULL OR consolidado_en IS NOT NULL", name="ck_turno_realizador_consolidado"
        ),
        Index("ix_turno_inicio", "inicio"),
        Index("ix_turno_asignado", "asignado_id"),
        Index("ix_turno_sin_consolidar", "fin", postgresql_where=text("consolidado_en IS NULL")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    horario_id: Mapped[int] = mapped_column(ForeignKey("horario_pactado.id"))
    fecha: Mapped[date]
    version_id: Mapped[int]
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    titular_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    asignado_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    realizador_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    sin_cobertura_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consolidado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EstadoVacante(str, enum.Enum):
    ABIERTA = "ABIERTA"
    RETIRADA = "RETIRADA"
    CUBIERTA = "CUBIERTA"
    SIN_COBERTURA = "SIN_COBERTURA"


class Vacante(Base):
    """Aviso de ausencia sobre un turno (D15). Como máximo una abierta por turno.

    motivo es visible solo para coordinadores (D25): la API lo filtra según el rol.
    urgente no se guarda: se calcula como inicio del turno - creada_en < 24 h.
    creada_en y cerrada_en los completa la aplicación con el reloj inyectable (D27).
    """

    __tablename__ = "vacante"
    __table_args__ = (
        CheckConstraint("(estado = 'ABIERTA') = (cerrada_en IS NULL)", name="ck_vacante_cierre"),
        Index(
            "ux_vacante_abierta_por_turno", "turno_id", unique=True, postgresql_where=text("estado = 'ABIERTA'")
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    turno_id: Mapped[int] = mapped_column(ForeignKey("turno.id"))
    generada_por_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    motivo: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[EstadoVacante] = mapped_column(
        Enum(EstadoVacante, name="estado_vacante"), server_default=EstadoVacante.ABIERTA.value
    )
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cerrada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Postulacion(Base):
    """Oferta de un médico para cubrir un turno, no una vacante (D16).

    Única por (turno, médico) aunque esté retirada: volver a postularse reactiva la misma fila.
    creada_en es la hora del servidor que desempata el orden de candidatos (D17).
    """

    __tablename__ = "postulacion"
    __table_args__ = (
        UniqueConstraint("turno_id", "medico_id", name="ux_postulacion_turno_medico"),
        Index("ix_postulacion_medico", "medico_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    turno_id: Mapped[int] = mapped_column(ForeignKey("turno.id"))
    medico_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retirada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

from datetime import date, datetime, time

from sqlalchemy import CheckConstraint, Computed, DateTime, ForeignKey, SmallInteger, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import DATERANGE, ExcludeConstraint, Range
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modelos.base import Base
from app.modelos.usuario import Usuario


class HorarioPactado(Base):
    """Identidad estable de un horario semanal (D09, D10). Los datos viven en sus versiones."""

    __tablename__ = "horario_pactado"

    id: Mapped[int] = mapped_column(primary_key=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    versiones: Mapped[list["VersionHorario"]] = relationship(
        back_populates="horario", order_by="VersionHorario.vigente_desde"
    )


class VersionHorario(Base):
    """Versión de un horario pactado con vigencia [vigente_desde, vigente_hasta) (D10, D14, D24)."""

    __tablename__ = "version_horario"
    __table_args__ = (
        CheckConstraint("dia_semana BETWEEN 1 AND 7", name="ck_version_horario_dia_semana"),
        CheckConstraint("duracion_horas BETWEEN 1 AND 24", name="ck_version_horario_duracion"),
        CheckConstraint("frecuencia_semanas >= 1", name="ck_version_horario_frecuencia"),
        CheckConstraint("extract(isodow FROM fecha_ancla) = 1", name="ck_version_horario_ancla_lunes"),
        CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta > vigente_desde", name="ck_version_horario_vigencia"
        ),
        ExcludeConstraint(
            ("horario_id", "="), ("vigencia", "&&"), name="ex_version_horario_vigencia", using="gist"
        ),
        UniqueConstraint("id", "horario_id", name="ux_version_horario_id_horario"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    horario_id: Mapped[int] = mapped_column(ForeignKey("horario_pactado.id"))
    medico_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), index=True)
    dia_semana: Mapped[int] = mapped_column(SmallInteger)
    hora_inicio: Mapped[time]
    duracion_horas: Mapped[int] = mapped_column(SmallInteger)
    frecuencia_semanas: Mapped[int] = mapped_column(SmallInteger)
    fecha_ancla: Mapped[date]
    vigente_desde: Mapped[date]
    vigente_hasta: Mapped[date | None]
    vigencia: Mapped[Range[date]] = mapped_column(
        DATERANGE, Computed("daterange(vigente_desde, vigente_hasta, '[)')", persisted=True)
    )

    horario: Mapped[HorarioPactado] = relationship(back_populates="versiones")
    medico: Mapped[Usuario | None] = relationship()

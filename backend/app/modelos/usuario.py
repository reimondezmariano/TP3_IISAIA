import enum
import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, Index, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base


class RolUsuario(str, enum.Enum):
    MEDICO = "MEDICO"
    COORDINADOR = "COORDINADOR"


class EstadoUsuario(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    ACTIVO = "ACTIVO"
    BAJA = "BAJA"


class Usuario(Base):
    __tablename__ = "usuario"
    __table_args__ = (
        CheckConstraint("(estado = 'BAJA') = (fecha_baja IS NOT NULL)", name="ck_usuario_fecha_baja"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text)
    rol: Mapped[RolUsuario] = mapped_column(Enum(RolUsuario, name="rol_usuario"))
    estado: Mapped[EstadoUsuario] = mapped_column(
        Enum(EstadoUsuario, name="estado_usuario"), server_default=EstadoUsuario.PENDIENTE.value
    )
    fecha_baja: Mapped[date | None]
    auth_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, unique=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


Index("ux_usuario_email_lower", func.lower(Usuario.email), unique=True)

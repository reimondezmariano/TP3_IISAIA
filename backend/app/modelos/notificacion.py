from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base


class Notificacion(Base):
    """Aviso dentro de la app para un usuario (D05). Se escribe en la misma transacción que la acción (D22).

    tipo es texto en MAYÚSCULAS (por ejemplo VACANTE_URGENTE); la lista la fija F4 sin cambiar el esquema.
    """

    __tablename__ = "notificacion"
    __table_args__ = (Index("ix_notificacion_usuario", "usuario_id", "creada_en"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    tipo: Mapped[str] = mapped_column(Text)
    mensaje: Mapped[str] = mapped_column(Text)
    turno_id: Mapped[int | None] = mapped_column(ForeignKey("turno.id"))
    datos: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    leida_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

from datetime import date

from sqlalchemy import CheckConstraint, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base


class EstadoConsolidacion(Base):
    """Marca de la consolidación perezosa (D20). Una sola fila, con id 1.

    Los turnos calculados con fecha anterior a consolidado_hasta ya se guardaron y consolidaron. La fila se
    bloquea en cada consolidación: dos consultas simultáneas se esperan (regla 8). El seed la vacía.
    """

    __tablename__ = "consolidacion_estado"
    __table_args__ = (CheckConstraint("id = 1", name="ck_consolidacion_estado_unica"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    consolidado_hasta: Mapped[date | None]

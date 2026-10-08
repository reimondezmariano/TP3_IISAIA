from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import Notificacion, Turno


def listar_de(
    sesion: Session, usuario_id: int, solo_no_leidas: bool, limite: int
) -> list[tuple[Notificacion, int | None, date | None]]:
    """Notificaciones del usuario, más nuevas primero, con el horario y la fecha de su turno (para el id de D09)."""
    consulta = (
        select(Notificacion, Turno.horario_id, Turno.fecha)
        .outerjoin(Turno, Notificacion.turno_id == Turno.id)
        .where(Notificacion.usuario_id == usuario_id)
    )
    if solo_no_leidas:
        consulta = consulta.where(Notificacion.leida_en.is_(None))
    consulta = consulta.order_by(Notificacion.creada_en.desc(), Notificacion.id.desc()).limit(limite)
    return [tuple(fila) for fila in sesion.execute(consulta).all()]

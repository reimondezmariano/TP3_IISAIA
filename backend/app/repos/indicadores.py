from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modelos import Turno


def sin_cobertura_por_mes(sesion: Session, desde: date, hasta_exclusive: date) -> dict[str, tuple[float, int]]:
    """Horas y cantidad de turnos consolidados sin realizador, por mes de la fecha de inicio (D13, D19, D24)."""
    mes = func.to_char(Turno.fecha, "YYYY-MM")
    consulta = (
        select(mes, func.sum(func.extract("epoch", Turno.fin - Turno.inicio)), func.count())
        .where(
            Turno.consolidado_en.is_not(None),
            Turno.realizador_id.is_(None),
            Turno.fecha >= desde,
            Turno.fecha < hasta_exclusive,
        )
        .group_by(mes)
    )
    return {fila[0]: (round(float(fila[1]) / 3600, 1), fila[2]) for fila in sesion.execute(consulta).all()}

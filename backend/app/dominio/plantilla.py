"""Reglas de la plantilla de horarios pactados (D10, D12, D14, D24). Lógica pura: sin base de datos ni FastAPI."""

import enum
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from app.errores import ErrorDominio


@dataclass(frozen=True)
class Vigencia:
    """Lo que las reglas necesitan de una versión: su titular y su vigencia [desde, hasta)."""

    version_id: int
    medico_id: int | None
    vigente_desde: date
    vigente_hasta: date | None

    def rige(self, fecha: date) -> bool:
        return self.vigente_desde <= fecha and (self.vigente_hasta is None or fecha < self.vigente_hasta)


class EstadoHorario(str, enum.Enum):
    CON_TITULAR = "CON_TITULAR"
    SIN_TITULAR = "SIN_TITULAR"  # la interfaz lo muestra con la etiqueta BAJA (D24)
    CERRADO = "CERRADO"


def lunes_de(fecha: date) -> date:
    return fecha - timedelta(days=fecha.weekday())


def validar_fecha_ancla(fecha_ancla: date) -> None:
    if fecha_ancla.isoweekday() != 1:
        raise ErrorDominio("FECHA_ANCLA_NO_LUNES", "La fecha ancla tiene que ser un lunes (D14).")


def validar_desde(desde: date, hoy: date) -> None:
    """Un cambio de plantilla nunca empieza en el pasado: reescribiría turnos que ya ocurrieron (D12)."""
    if desde < hoy:
        raise ErrorDominio("FECHA_PASADA", f"El cambio no puede empezar antes de hoy ({hoy:%d/%m/%Y}).")


def version_que_cubre(vigencias: Sequence[Vigencia], desde: date, horario_id: int) -> Vigencia:
    """Versión que se parte en `desde` para abrir otra (D10). La nueva hereda su fin de vigencia."""
    cubre = next((v for v in vigencias if v.rige(desde)), None)
    if cubre is None:
        raise ErrorDominio(
            "HORARIO_SIN_VIGENCIA",
            f"El horario {horario_id} no rige el {desde:%d/%m/%Y}: está cerrado o todavía no empezó.",
            409,
        )
    if cubre.vigente_desde == desde:
        raise ErrorDominio(
            "VERSION_EN_ESA_FECHA", f"El horario {horario_id} ya tiene una versión que empieza el {desde:%d/%m/%Y}.", 409
        )
    return cubre


def version_a_modificar(
    vigencias: Sequence[Vigencia], desde: date, horario_id: int, hoy: date
) -> tuple[Vigencia, bool]:
    """Versión sobre la que se aplica un cambio desde `desde`, y si se modifica en el lugar (D10).

    Una versión que empieza justo en `desde` y todavía no rige (empieza después de hoy) se modifica en el
    lugar: nunca rigió, así que no tiene historia que conservar. En cualquier otro caso se parte la versión
    que rige ese día.
    """
    rige = next((v for v in vigencias if v.rige(desde)), None)
    if rige is not None and rige.vigente_desde == desde and desde > hoy:
        return rige, True
    return version_que_cubre(vigencias, desde, horario_id), False


def hay_version_posterior(vigencias: Sequence[Vigencia], desde: date) -> bool:
    return any(v.vigente_desde > desde for v in vigencias)


def estado_horario(vigencias: Sequence[Vigencia], hoy: date) -> EstadoHorario:
    """Se calcula, no se guarda (D08): según la versión que rige hoy o, si todavía no empezó, la próxima."""
    referencia = next((v for v in vigencias if v.rige(hoy)), None)
    if referencia is None:
        futuras = sorted((v for v in vigencias if v.vigente_desde > hoy), key=lambda v: v.vigente_desde)
        referencia = futuras[0] if futuras else None
    if referencia is None:
        return EstadoHorario.CERRADO
    return EstadoHorario.SIN_TITULAR if referencia.medico_id is None else EstadoHorario.CON_TITULAR

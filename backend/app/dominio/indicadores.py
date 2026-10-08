"""Rango de meses del indicador de horas sin cobertura (D19). Lógica pura: sin base de datos ni FastAPI."""

from datetime import date

from app.errores import ErrorDominio

MAX_MESES = 24


def _indice(mes: str) -> int:
    anio, numero = mes.split("-")
    return int(anio) * 12 + int(numero) - 1


def _mes(indice: int) -> str:
    return f"{indice // 12:04d}-{indice % 12 + 1:02d}"


def meses_del_rango(desde: str, hasta: str) -> list[str]:
    """Meses "AAAA-MM" de desde a hasta, inclusive. Los formatos ya los validó la API."""
    inicio, fin = _indice(desde), _indice(hasta)
    if fin < inicio:
        raise ErrorDominio("RANGO_INVALIDO", "El mes 'hasta' no puede ser anterior a 'desde'.")
    if fin - inicio + 1 > MAX_MESES:
        raise ErrorDominio("RANGO_DEMASIADO_GRANDE", f"El rango no puede superar {MAX_MESES} meses.")
    return [_mes(i) for i in range(inicio, fin + 1)]


def primer_dia(mes: str) -> date:
    return date(int(mes[:4]), int(mes[5:]), 1)


def primer_dia_siguiente(mes: str) -> date:
    return primer_dia(_mes(_indice(mes) + 1))

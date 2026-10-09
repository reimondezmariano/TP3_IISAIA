"""Tipos y textos de las notificaciones dentro de la app (D05). Lógica pura: sin base de datos ni FastAPI."""

from datetime import datetime
from enum import Enum

from app.dominio.alertas import Umbral
from app.dominio.tiempo import exigir_zona


class TipoNotificacion(str, Enum):
    """Lista cerrada de tipos (la columna es texto: agregar uno no necesita migración)."""

    VACANTE_URGENTE = "VACANTE_URGENTE"  # D05, D15: la crea generar_vacante (F3, Mariano)
    VACANTE_ABIERTA = "VACANTE_ABIERTA"  # vacante que no es urgente: solo campanita, sin aviso emergente
    ALERTA_SIN_COBERTURA = "ALERTA_SIN_COBERTURA"  # D19
    TURNO_ASIGNADO = "TURNO_ASIGNADO"  # D18: al médico a quien el coordinador asigna el turno
    NUEVO_REGISTRO = "NUEVO_REGISTRO"  # D30: a los coordinadores, cuando alguien queda PENDIENTE al registrarse


_CUANDO = {
    Umbral.HORAS_48: "empieza en 48 h",
    Umbral.HORAS_24: "empieza en 24 h",
    Umbral.INICIO: "ya empezó",
}


def mensaje_alerta(umbral: Umbral, inicio: datetime) -> str:
    """Texto de la alerta a coordinadores. `inicio` tiene que venir en la zona del servicio."""
    exigir_zona(inicio)
    return f"La guardia del {inicio:%d/%m} a las {inicio:%H:%M} sigue sin cobertura: {_CUANDO[umbral]}."


def mensaje_nuevo_registro(nombre: str) -> str:
    """Texto del aviso a coordinadores de que una cuenta espera activación (D30)."""
    return f"{nombre} se registró y espera activación"

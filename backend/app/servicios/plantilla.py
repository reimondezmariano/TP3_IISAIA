"""Operaciones sobre la plantilla (D10, D12, D23, D24). Combinan reglas de dominio y repos; no hacen commit.

Orden de bloqueos: primero el usuario, después el horario. La baja y el cambio de rol también lo siguen,
para que dos operaciones simultáneas no se esperen en cruz.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.dominio.plantilla import hay_version_posterior, validar_desde, validar_fecha_ancla, version_que_cubre
from app.errores import ErrorDominio
from app.modelos import EstadoUsuario, HorarioPactado, RolUsuario, Usuario, VersionHorario
from app.repos.horarios import (
    DatosVersion,
    TurnoAfectado,
    a_vigencia,
    bloquear_horario,
    crear_horario,
    datos_de,
    nueva_version,
    turnos_afectados,
)
from app.repos.usuarios import bloquear_usuario


def validar_titular(sesion: Session, medico_id: int) -> Usuario:
    """El titular es un médico activo (D23). Queda bloqueado: una baja o un cambio de rol en paralelo espera."""
    medico = bloquear_usuario(sesion, medico_id)
    if medico is None or medico.rol != RolUsuario.MEDICO or medico.estado != EstadoUsuario.ACTIVO:
        raise ErrorDominio("TITULAR_INVALIDO", "El titular tiene que ser un médico activo (D23).")
    return medico


def crear_horario_pactado(sesion: Session, datos: DatosVersion, vigente_desde: date, hoy: date) -> HorarioPactado:
    validar_desde(vigente_desde, hoy)
    validar_fecha_ancla(datos.fecha_ancla)
    validar_titular(sesion, datos.medico_id)
    return crear_horario(sesion, datos, vigente_desde)


@dataclass(frozen=True)
class ResultadoVersion:
    version: VersionHorario
    turnos_afectados: list[TurnoAfectado]


def _partir(
    sesion: Session, horario_id: int, versiones: list[VersionHorario], cambios: Mapping[str, Any], desde: date
) -> VersionHorario:
    """Abre en `desde` una versión con `cambios`; lo demás se copia de la versión que rige ese día."""
    cubre_id = version_que_cubre([a_vigencia(v) for v in versiones], desde, horario_id).version_id
    actuales = datos_de(next(v for v in versiones if v.id == cubre_id))
    nuevos = replace(actuales, **cambios)
    if nuevos == actuales:
        raise ErrorDominio("SIN_CAMBIOS", "La versión nueva es igual a la que rige ese día.")
    validar_fecha_ancla(nuevos.fecha_ancla)
    return nueva_version(sesion, horario_id, nuevos, desde)


def abrir_version(
    sesion: Session, horario_id: int, cambios: Mapping[str, Any], desde: date, hoy: date
) -> ResultadoVersion:
    """Renegociación, designación de titular o horario sin titular, desde `desde` (D10, D12, D24).

    `cambios` usa los nombres de DatosVersion; medico_id None deja el horario sin titular.
    """
    validar_desde(desde, hoy)
    if cambios.get("medico_id") is not None:
        validar_titular(sesion, cambios["medico_id"])  # primero el usuario, después el horario
    versiones = bloquear_horario(sesion, horario_id)
    if versiones is None:
        raise ErrorDominio("HORARIO_NO_ENCONTRADO", "No existe ese horario.", 404)
    version = _partir(sesion, horario_id, versiones, cambios, desde)
    return ResultadoVersion(version, turnos_afectados(sesion, [horario_id], desde))


def cerrar_horario(sesion: Session, horario_id: int, desde: date, hoy: date) -> list[TurnoAfectado]:
    """El horario deja de regir en `desde` (D24). No borra versiones: corta la vigencia de la que rige ese día."""
    validar_desde(desde, hoy)
    versiones = bloquear_horario(sesion, horario_id)
    if versiones is None:
        raise ErrorDominio("HORARIO_NO_ENCONTRADO", "No existe ese horario.", 404)
    vigencias = [a_vigencia(v) for v in versiones]
    cubre_id = version_que_cubre(vigencias, desde, horario_id).version_id
    if hay_version_posterior(vigencias, desde):
        raise ErrorDominio(
            "VERSION_POSTERIOR_EXISTENTE",
            f"El horario {horario_id} tiene una versión que empieza después del {desde:%d/%m/%Y}: cerrarlo la dejaría suelta.",
            409,
        )
    next(v for v in versiones if v.id == cubre_id).vigente_hasta = desde
    sesion.flush()
    return turnos_afectados(sesion, [horario_id], desde)

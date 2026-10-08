"""Operaciones sobre la plantilla (D10, D12, D23, D24). Combinan reglas de dominio y repos; no hacen commit.

Orden de bloqueos: primero el usuario, después el horario. La baja y el cambio de rol también lo siguen,
para que dos operaciones simultáneas no se esperen en cruz.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.dominio.plantilla import (
    hay_version_posterior,
    validar_desde,
    validar_fecha_ancla,
    version_a_modificar,
    version_que_cubre,
)
from app.errores import ErrorDominio
from app.modelos import EstadoUsuario, HorarioPactado, RolUsuario, Usuario, VersionHorario
from app.repos.horarios import (
    DatosVersion,
    TurnoAfectado,
    a_vigencia,
    bloquear_horario,
    crear_horario,
    datos_de,
    modificar_version,
    nueva_version,
    turnos_afectados,
    versiones_del_medico_desde,
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
    sesion: Session,
    horario_id: int,
    versiones: list[VersionHorario],
    cambios: Mapping[str, Any],
    desde: date,
    hoy: date,
) -> VersionHorario:
    """Aplica `cambios` desde `desde`; lo demás se copia de la versión que rige ese día.

    Parte esa versión y abre otra, salvo que empiece justo en `desde` y todavía no rija: entonces la modifica
    en el lugar (D10).
    """
    vigencia, en_el_lugar = version_a_modificar([a_vigencia(v) for v in versiones], desde, horario_id, hoy)
    version = next(v for v in versiones if v.id == vigencia.version_id)
    actuales = datos_de(version)
    nuevos = replace(actuales, **cambios)
    if nuevos == actuales:
        raise ErrorDominio("SIN_CAMBIOS", "La versión nueva es igual a la que rige ese día.")
    validar_fecha_ancla(nuevos.fecha_ancla)
    if en_el_lugar:
        return modificar_version(sesion, version, nuevos)
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
    version = _partir(sesion, horario_id, versiones, cambios, desde, hoy)
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


def dejar_sin_titular(
    sesion: Session, medico_id: int, desde: date, hoy: date
) -> tuple[list[int], list[TurnoAfectado]]:
    """Deja sin titular, desde `desde`, cada horario del médico (D23, D24): parte la versión que rige ese día y
    pasa a sin titular, en el lugar, las versiones propias que todavía no rigen.

    Quien llama ya bloqueó al médico: nadie puede designarlo titular mientras tanto. La lista de horarios se
    lee sin bloquearlos, así que cada uno se vuelve a mirar después de bloquearlo: si mientras tanto otro
    coordinador designó a alguien más, ese horario ya no es del médico y no se toca (regla 8).
    """
    validar_desde(desde, hoy)
    candidatos = sorted({v.horario_id for v in versiones_del_medico_desde(sesion, medico_id, desde)})
    horario_ids = []
    for horario_id in candidatos:
        versiones = bloquear_horario(sesion, horario_id)
        tocado = False
        # Versiones propias que todavía no rigen (empiezan en `desde` o después): se dejan sin titular en el lugar.
        for futura in [v for v in versiones if v.medico_id == medico_id and v.vigente_desde >= desde]:
            _partir(sesion, horario_id, versiones, {"medico_id": None}, futura.vigente_desde, hoy)
            tocado = True
        rige = next((v for v in versiones if a_vigencia(v).rige(desde)), None)
        if rige is not None and rige.medico_id == medico_id:
            _partir(sesion, horario_id, versiones, {"medico_id": None}, desde, hoy)
            tocado = True
        if tocado:
            horario_ids.append(horario_id)
    return horario_ids, turnos_afectados(sesion, horario_ids, desde)

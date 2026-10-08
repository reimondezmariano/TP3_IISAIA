"""Operaciones sobre la plantilla (D10, D12, D23, D24). Combinan reglas de dominio y repos; no hacen commit.

Orden de bloqueos: primero el usuario, después el horario. La baja y el cambio de rol también lo siguen,
para que dos operaciones simultáneas no se esperen en cruz.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.dominio.plantilla import validar_desde, validar_fecha_ancla
from app.errores import ErrorDominio
from app.modelos import EstadoUsuario, HorarioPactado, RolUsuario, Usuario
from app.repos.horarios import DatosVersion, crear_horario
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

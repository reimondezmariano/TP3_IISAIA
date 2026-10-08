import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.modelos import EstadoUsuario, RolUsuario, Usuario


def buscar_por_auth_id(sesion: Session, auth_id: uuid.UUID) -> Usuario | None:
    return sesion.scalar(select(Usuario).where(Usuario.auth_id == auth_id))


def buscar_por_email(sesion: Session, email: str) -> Usuario | None:
    """Sin distinguir mayúsculas, como el índice único ux_usuario_email_lower."""
    return sesion.scalar(select(Usuario).where(func.lower(Usuario.email) == email.lower()))


def listar_usuarios(sesion: Session) -> list[Usuario]:
    """Todos, en cualquier estado: nunca se borra un usuario (D24)."""
    return list(sesion.scalars(select(Usuario).order_by(Usuario.nombre, Usuario.id)))


def bloquear_usuario(sesion: Session, usuario_id: int) -> Usuario | None:
    """Bloquea la fila hasta el fin de la transacción (regla 8) y la relee de la base."""
    return sesion.scalar(
        select(Usuario)
        .where(Usuario.id == usuario_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def bloquear_con_coordinadores(sesion: Session, usuario_id: int) -> tuple[Usuario | None, list[Usuario]]:
    """Bloquea, en orden de id, al usuario y a los coordinadores activos (D23, regla 8).

    Un solo SELECT ... ORDER BY id FOR UPDATE: dos cambios de rol simultáneos toman los bloqueos en el
    mismo orden (sin deadlock) y el segundo, al despertar, vuelve a evaluar el WHERE y ya no cuenta a quien
    dejó de ser coordinador.
    """
    filas = sesion.scalars(
        select(Usuario)
        .where(
            or_(
                Usuario.id == usuario_id,
                and_(Usuario.rol == RolUsuario.COORDINADOR, Usuario.estado == EstadoUsuario.ACTIVO),
            )
        )
        .order_by(Usuario.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    usuario = next((u for u in filas if u.id == usuario_id), None)
    coordinadores = [u for u in filas if u.rol == RolUsuario.COORDINADOR and u.estado == EstadoUsuario.ACTIVO]
    return usuario, coordinadores

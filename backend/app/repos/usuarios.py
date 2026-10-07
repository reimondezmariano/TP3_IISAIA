import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modelos import Usuario


def buscar_por_auth_id(sesion: Session, auth_id: uuid.UUID) -> Usuario | None:
    return sesion.scalar(select(Usuario).where(Usuario.auth_id == auth_id))


def buscar_por_email(sesion: Session, email: str) -> Usuario | None:
    """Sin distinguir mayúsculas, como el índice único ux_usuario_email_lower."""
    return sesion.scalar(select(Usuario).where(func.lower(Usuario.email) == email.lower()))

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import Usuario


def buscar_por_auth_id(sesion: Session, auth_id: uuid.UUID) -> Usuario | None:
    return sesion.scalar(select(Usuario).where(Usuario.auth_id == auth_id))

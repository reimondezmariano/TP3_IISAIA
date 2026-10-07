from itertools import count

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modelos import EstadoUsuario, RolUsuario, Usuario

_secuencia = count(1)


def crear_usuario(
    sesion: Session,
    nombre: str,
    rol: RolUsuario = RolUsuario.MEDICO,
    estado: EstadoUsuario = EstadoUsuario.ACTIVO,
    email: str | None = None,
) -> Usuario:
    usuario = Usuario(
        nombre=nombre,
        email=email or f"usuario{next(_secuencia)}@prueba.test",
        rol=rol,
        estado=estado,
    )
    sesion.add(usuario)
    sesion.flush()
    return usuario


def guardar(sesion: Session, objeto) -> None:
    sesion.add(objeto)
    sesion.flush()


def debe_fallar(sesion: Session, objeto, restriccion: str) -> None:
    """Verifica que guardar el objeto viola exactamente la restricción indicada, sin romper la sesión."""
    with pytest.raises(IntegrityError) as excinfo:
        with sesion.begin_nested():
            guardar(sesion, objeto)
    assert excinfo.value.orig.diag.constraint_name == restriccion

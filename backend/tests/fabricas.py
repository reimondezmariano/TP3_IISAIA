from itertools import count

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

from fastapi import APIRouter, Depends

from app.api.esquemas import Esquema
from app.auth import usuario_registrado
from app.modelos import EstadoUsuario, RolUsuario, Usuario

router = APIRouter()


class UsuarioOut(Esquema):
    id: int
    nombre: str
    email: str
    rol: RolUsuario
    estado: EstadoUsuario


def _a_salida(usuario: Usuario) -> UsuarioOut:
    return UsuarioOut(
        id=usuario.id, nombre=usuario.nombre, email=usuario.email, rol=usuario.rol, estado=usuario.estado
    )


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(usuario_registrado)) -> UsuarioOut:
    """Usuario de la sesión, en cualquier estado: la interfaz muestra "esperando activación" si está PENDIENTE."""
    return _a_salida(usuario)

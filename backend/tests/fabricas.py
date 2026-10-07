import time
import uuid
from datetime import timedelta
from itertools import count

import jwt
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
    con_cuenta: bool = True,
) -> Usuario:
    usuario = Usuario(
        nombre=nombre,
        email=email or f"usuario{next(_secuencia)}@prueba.test",
        rol=rol,
        estado=estado,
        auth_id=uuid.uuid4() if con_cuenta else None,
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


SECRETO_PRUEBA = "secreto-de-prueba-de-guardia-viva-de-32-bytes-o-mas"


def token_para(
    auth_id,
    email: str | None = "medico@prueba.test",
    vence_en: timedelta = timedelta(hours=1),
    clave=SECRETO_PRUEBA,
    algoritmo: str = "HS256",
    **claims,
) -> str:
    """Token de acceso como los de Supabase Auth. Un claim en None se omite.

    Usa la hora real: PyJWT controla el vencimiento con ella (ver "Decisiones de este plan" en el plan de F2).
    """
    ahora = int(time.time())
    carga = {
        "sub": str(auth_id),
        "email": email,
        "aud": "authenticated",
        "role": "authenticated",
        "iat": ahora,
        "exp": ahora + int(vence_en.total_seconds()),
    }
    carga.update(claims)
    return jwt.encode({k: v for k, v in carga.items() if v is not None}, clave, algorithm=algoritmo)


def encabezados(usuario) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_para(usuario.auth_id, email=usuario.email)}"}

"""Autenticación con Supabase Auth (D06) y permisos por estado y rol (D23, D30).

El frontend inicia sesión contra Supabase Auth y manda el token de acceso en Authorization: Bearer.
El backend solo verifica el token: nunca ve ni guarda contraseñas.
Dependencias, de menor a mayor exigencia: identidad_actual (token válido), usuario_registrado
(token vinculado a un Usuario), usuario_actual (Usuario ACTIVO, o BAJA hasta su fecha de baja inclusive),
requiere_coordinador.
"""

import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errores import ErrorDominio
from app.modelos import EstadoUsuario, RolUsuario, Usuario
from app.reloj import Reloj, get_reloj, hoy
from app.repos.usuarios import buscar_por_auth_id

AUDIENCIA = "authenticated"
ALGORITMOS_CON_SECRETO = ("HS256",)
ALGORITMOS_CON_CLAVE_PUBLICA = ("ES256", "RS256")


@dataclass(frozen=True)
class Identidad:
    """Lo que el token garantiza sobre quien llama: su cuenta de Supabase Auth y su email."""

    auth_id: uuid.UUID
    email: str | None


class FuenteDeClaves(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> Any: ...


def _token_invalido() -> ErrorDominio:
    return ErrorDominio("TOKEN_INVALIDO", "El token de sesión no es válido.", 401)


class VerificadorToken:
    """Verifica firma, audiencia y vencimiento de un token de acceso de Supabase Auth.

    La clave depende del algoritmo del token: el secreto para HS256, las claves públicas (JWKS) del
    proyecto para ES256 y RS256. Cualquier otro algoritmo, incluido "none", se rechaza.
    El vencimiento lo controla PyJWT con la hora real, no con el reloj inyectable: Supabase emite el
    token en tiempo real, y adelantar el reloj de demo (D27) no debe cerrar las sesiones.
    """

    def __init__(self, secreto: str | None = None, jwks: FuenteDeClaves | None = None) -> None:
        self._secreto = secreto
        self._jwks = jwks

    def verificar(self, token: str) -> Identidad:
        try:
            algoritmo = jwt.get_unverified_header(token).get("alg")
            claims = jwt.decode(
                token,
                self._clave(token, algoritmo),
                algorithms=[algoritmo],
                audience=AUDIENCIA,
                options={"require": ["exp", "sub", "aud"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise ErrorDominio("TOKEN_VENCIDO", "La sesión venció. Volvé a ingresar.", 401) from exc
        except jwt.PyJWKClientConnectionError as exc:
            raise ErrorDominio(
                "AUTH_NO_DISPONIBLE", "No se pudo consultar Supabase Auth para verificar la sesión.", 503
            ) from exc
        except jwt.PyJWTError as exc:
            raise _token_invalido() from exc
        try:
            auth_id = uuid.UUID(claims["sub"])
        except (ValueError, TypeError, AttributeError) as exc:
            raise _token_invalido() from exc
        email = claims.get("email")
        return Identidad(auth_id=auth_id, email=email if isinstance(email, str) and email else None)

    def _clave(self, token: str, algoritmo: str | None) -> Any:
        if algoritmo in ALGORITMOS_CON_SECRETO and self._secreto:
            return self._secreto
        if algoritmo in ALGORITMOS_CON_CLAVE_PUBLICA and self._jwks is not None:
            return self._jwks.get_signing_key_from_jwt(token).key
        raise jwt.InvalidAlgorithmError(f"Algoritmo no aceptado: {algoritmo}")


@lru_cache
def _cliente_jwks(supabase_url: str) -> jwt.PyJWKClient:
    """Un cliente por proyecto: guarda en memoria las claves públicas y las renueva solo si aparece una nueva."""
    return jwt.PyJWKClient(f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json")


def get_verificador() -> VerificadorToken:
    settings = get_settings()
    if not (settings.supabase_url or settings.supabase_jwt_secret):
        raise ErrorDominio(
            "AUTH_NO_CONFIGURADA", "Falta configurar SUPABASE_URL o SUPABASE_JWT_SECRET en el servidor.", 503
        )
    jwks = _cliente_jwks(settings.supabase_url) if settings.supabase_url else None
    return VerificadorToken(secreto=settings.supabase_jwt_secret or None, jwks=jwks)


_bearer = HTTPBearer(auto_error=False)


def identidad_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
    verificador: VerificadorToken = Depends(get_verificador),
) -> Identidad:
    if credenciales is None or not credenciales.credentials:
        raise ErrorDominio("SIN_SESION", "Falta el token de sesión.", 401)
    return verificador.verificar(credenciales.credentials)


def usuario_registrado(
    identidad: Identidad = Depends(identidad_actual), db: Session = Depends(get_db)
) -> Usuario:
    """Usuario vinculado al token, en cualquier estado. Solo para GET /me."""
    usuario = buscar_por_auth_id(db, identidad.auth_id)
    if usuario is None:
        raise ErrorDominio("USUARIO_NO_REGISTRADO", "La cuenta todavía no completó el registro.", 403)
    return usuario


def usuario_actual(usuario: Usuario = Depends(usuario_registrado), reloj: Reloj = Depends(get_reloj)) -> Usuario:
    """Usuario con acceso (D23, D30). Lo exige todo endpoint salvo /health, /me y /registro.

    Una baja (D24) deja entrar hasta la fecha de baja inclusive: el estado pasa a BAJA al registrarla,
    pero el médico todavía trabaja hasta ese día.
    """
    if usuario.estado == EstadoUsuario.PENDIENTE:
        raise ErrorDominio("CUENTA_PENDIENTE", "Un coordinador tiene que activar tu cuenta.", 403)
    if usuario.estado == EstadoUsuario.BAJA and usuario.fecha_baja < hoy(reloj):
        raise ErrorDominio("CUENTA_DADA_DE_BAJA", "La cuenta está dada de baja.", 403)
    return usuario


def requiere_coordinador(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
    """Permiso validado en el backend aunque la interfaz oculte la acción (regla 7)."""
    if usuario.rol != RolUsuario.COORDINADOR:
        raise ErrorDominio("SIN_PERMISO", "Solo un coordinador puede hacer esta acción.", 403)
    return usuario

import datetime as dt
import time
import uuid
from datetime import date, timedelta
from itertools import count
from zoneinfo import ZoneInfo

import jwt
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modelos import EstadoUsuario, HorarioPactado, RolUsuario, Usuario
from app.repos.horarios import DatosVersion, crear_horario

_secuencia = count(1)


def crear_usuario(
    sesion: Session,
    nombre: str,
    rol: RolUsuario = RolUsuario.MEDICO,
    estado: EstadoUsuario = EstadoUsuario.ACTIVO,
    email: str | None = None,
    con_cuenta: bool = True,
    fecha_baja: date | None = None,
) -> Usuario:
    if estado == EstadoUsuario.BAJA and fecha_baja is None:
        fecha_baja = date(2000, 1, 1)  # baja vieja: ya no entra con ningún reloj
    usuario = Usuario(
        nombre=nombre,
        email=email or f"usuario{next(_secuencia)}@prueba.test",
        rol=rol,
        estado=estado,
        fecha_baja=fecha_baja,
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


ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
HOY = date(2026, 10, 12)  # fecha del RelojFijo de conftest (lunes 12/10/2026 09:00)


def crear_horario_de_prueba(
    sesion: Session,
    medico_id: int | None,
    dia: int = 2,
    hora: dt.time = dt.time(8),
    dur: int = 12,
    frec: int = 1,
    ancla: date = date(2026, 9, 7),
    desde: date = date(2026, 9, 7),
    hasta: date | None = None,
) -> HorarioPactado:
    """Por defecto: martes de 08:00 a 20:00 todas las semanas, vigente desde el 7/9."""
    datos = DatosVersion(
        medico_id=medico_id,
        dia_semana=dia,
        hora_inicio=hora,
        duracion_horas=dur,
        frecuencia_semanas=frec,
        fecha_ancla=ancla,
    )
    return crear_horario(sesion, datos, desde, hasta)

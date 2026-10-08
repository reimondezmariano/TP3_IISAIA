"""Notificaciones dentro de la app (D05). No hace commit: la notificación va en la transacción de la acción (D22)."""

from collections.abc import Collection, Iterable
from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.dominio.notificaciones import TipoNotificacion
from app.dominio.tiempo import exigir_zona
from app.errores import ErrorDominio
from app.modelos import EstadoUsuario, Notificacion, RolUsuario, Turno, Usuario


def notificar(
    sesion: Session,
    usuario_ids: Iterable[int],
    tipo: TipoNotificacion,
    mensaje: str,
    ahora: datetime,
    turno: Turno | None = None,
    datos: dict[str, Any] | None = None,
) -> list[Notificacion]:
    """Una notificación por destinatario (sin repetir), con creada_en = ahora del reloj inyectable (D27)."""
    exigir_zona(ahora)
    filas = [
        Notificacion(
            usuario_id=usuario_id,
            tipo=tipo.value,
            mensaje=mensaje,
            turno_id=turno.id if turno is not None else None,
            datos=dict(datos or {}),
            creada_en=ahora,
        )
        for usuario_id in dict.fromkeys(usuario_ids)
    ]
    sesion.add_all(filas)
    sesion.flush()
    return filas


def destinatarios(sesion: Session, rol: RolUsuario, dia: date, excepto: Collection[int] = ()) -> list[int]:
    """Ids de quienes tienen acceso ese día: ACTIVO, o BAJA hasta su fecha de baja inclusive (D24)."""
    consulta = (
        select(Usuario.id)
        .where(
            Usuario.rol == rol,
            or_(
                Usuario.estado == EstadoUsuario.ACTIVO,
                and_(Usuario.estado == EstadoUsuario.BAJA, Usuario.fecha_baja >= dia),
            ),
        )
        .order_by(Usuario.id)
    )
    return [usuario_id for usuario_id in sesion.scalars(consulta) if usuario_id not in excepto]


def marcar_leida(sesion: Session, notificacion_id: int, usuario: Usuario, ahora: datetime) -> Notificacion:
    """Marca como leída una notificación propia. Una ajena responde igual que una inexistente."""
    notificacion = sesion.scalar(
        select(Notificacion)
        .where(Notificacion.id == notificacion_id, Notificacion.usuario_id == usuario.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if notificacion is None:
        raise ErrorDominio("NOTIFICACION_NO_ENCONTRADA", "La notificación no existe.", 404)
    if notificacion.leida_en is None:
        notificacion.leida_en = ahora
        sesion.flush()
    return notificacion

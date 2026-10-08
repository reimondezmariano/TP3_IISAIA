from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.esquemas import Esquema
from app.auth import usuario_actual
from app.config import get_settings
from app.db import get_db
from app.dominio.calendario import formatear_id_turno
from app.modelos import Notificacion, Turno, Usuario
from app.reloj import Reloj, get_reloj
from app.repos.notificaciones import listar_de
from app.servicios.alertas import emitir_alertas
from app.servicios.notificaciones import marcar_leida

router = APIRouter()

LIMITE = 50


class NotificacionOut(Esquema):
    id: int
    tipo: str
    mensaje: str
    turno_id: str | None
    datos: dict[str, Any]
    creada_en: datetime
    leida_en: datetime | None


def _a_salida(notificacion: Notificacion, horario_id: int | None, fecha: date | None) -> NotificacionOut:
    zona = get_settings().zona
    return NotificacionOut(
        id=notificacion.id,
        tipo=notificacion.tipo,
        mensaje=notificacion.mensaje,
        turno_id=formatear_id_turno(horario_id, fecha) if horario_id is not None else None,
        datos=notificacion.datos,
        creada_en=notificacion.creada_en.astimezone(zona),
        leida_en=notificacion.leida_en.astimezone(zona) if notificacion.leida_en else None,
    )


@router.get("/notificaciones", response_model=list[NotificacionOut])
def listar(
    solo_no_leidas: bool = Query(False, alias="soloNoLeidas"),
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    usuario: Usuario = Depends(usuario_actual),
) -> list[NotificacionOut]:
    """Avisos dentro de la app (D05), más nuevos primero, hasta 50. La interfaz consulta cada 10 a 15 s.

    Antes de responder emite las alertas de D19 que vencieron: así llegan a tiempo sin proceso programado.
    """
    emitir_alertas(db, reloj, get_settings().zona)
    db.commit()
    return [_a_salida(*fila) for fila in listar_de(db, usuario.id, solo_no_leidas, LIMITE)]


@router.post("/notificaciones/{notificacion_id}/leida", response_model=NotificacionOut)
def leida(
    notificacion_id: int,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    usuario: Usuario = Depends(usuario_actual),
) -> NotificacionOut:
    notificacion = marcar_leida(db, notificacion_id, usuario, reloj.ahora())
    db.commit()
    turno = db.get(Turno, notificacion.turno_id) if notificacion.turno_id is not None else None
    return _a_salida(notificacion, turno.horario_id if turno else None, turno.fecha if turno else None)

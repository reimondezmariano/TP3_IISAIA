from datetime import date, time
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.esquemas import Esquema
from app.api.horarios import TurnoAfectadoOut, turno_afectado_out
from app.auth import requiere_coordinador
from app.db import get_db
from app.errores import ErrorDominio
from app.modelos import EstadoUsuario, RolUsuario, Usuario, VersionHorario
from app.reloj import Reloj, get_reloj, hoy
from app.repos.horarios import versiones_no_terminadas_por_medico
from app.repos.usuarios import listar_usuarios
from app.servicios.usuarios import ResultadoCambio, activar, cambiar_rol, dar_de_baja

router = APIRouter()


class HorarioDelMedicoOut(Esquema):
    horario_id: int
    dia_semana: int
    hora_inicio: time
    duracion_horas: int
    frecuencia_semanas: int
    fecha_ancla: date
    vigente_desde: date
    vigente_hasta: date | None


class UsuarioStaffOut(Esquema):
    id: int
    nombre: str
    email: str
    rol: RolUsuario
    estado: EstadoUsuario
    fecha_baja: date | None
    horarios: list[HorarioDelMedicoOut]


def _horario_del_medico(version: VersionHorario) -> HorarioDelMedicoOut:
    return HorarioDelMedicoOut(
        horario_id=version.horario_id,
        dia_semana=version.dia_semana,
        hora_inicio=version.hora_inicio,
        duracion_horas=version.duracion_horas,
        frecuencia_semanas=version.frecuencia_semanas,
        fecha_ancla=version.fecha_ancla,
        vigente_desde=version.vigente_desde,
        vigente_hasta=version.vigente_hasta,
    )


def usuario_out(usuario: Usuario, versiones: list[VersionHorario]) -> UsuarioStaffOut:
    return UsuarioStaffOut(
        id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
        rol=usuario.rol,
        estado=usuario.estado,
        fecha_baja=usuario.fecha_baja,
        horarios=[_horario_del_medico(v) for v in versiones],
    )


@router.get("/usuarios", response_model=list[UsuarioStaffOut])
def listar(
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> list[UsuarioStaffOut]:
    """Staff con rol, estado y horarios que rigen hoy o empiezan después (D26)."""
    por_medico = versiones_no_terminadas_por_medico(db, hoy(reloj))
    return [usuario_out(u, por_medico.get(u.id, [])) for u in listar_usuarios(db)]


class CambioUsuarioIn(Esquema):
    estado: Literal["ACTIVO"] | None = None  # la baja tiene su propia ruta
    rol: RolUsuario | None = None


class CambioUsuarioOut(Esquema):
    usuario: UsuarioStaffOut
    horarios_sin_titular: list[int]
    turnos_afectados: list[TurnoAfectadoOut]
    coberturas_reabiertas: list[TurnoAfectadoOut]


def cambio_out(db: Session, resultado: ResultadoCambio, dia: date) -> CambioUsuarioOut:
    usuario = resultado.usuario
    versiones = versiones_no_terminadas_por_medico(db, dia, usuario.id).get(usuario.id, [])
    return CambioUsuarioOut(
        usuario=usuario_out(usuario, versiones),
        horarios_sin_titular=resultado.horarios_sin_titular,
        turnos_afectados=[turno_afectado_out(t) for t in resultado.turnos_afectados],
        coberturas_reabiertas=[turno_afectado_out(t) for t in resultado.coberturas_reabiertas],
    )


@router.patch("/usuarios/{usuario_id}", response_model=CambioUsuarioOut)
def modificar(
    usuario_id: int,
    datos: CambioUsuarioIn,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    coordinador: Usuario = Depends(requiere_coordinador),
) -> CambioUsuarioOut:
    """Activa a un médico pendiente (D26, D30) y/o cambia el rol (D23), en ese orden."""
    if datos.estado is None and datos.rol is None:
        raise ErrorDominio("SIN_CAMBIOS", "No se pidió ningún cambio.")
    dia = hoy(reloj)
    if datos.rol is not None:
        resultado = cambiar_rol(db, usuario_id, datos.rol, coordinador, reloj, activar_antes=datos.estado is not None)
    else:
        resultado = activar(db, usuario_id)
    db.commit()
    return cambio_out(db, resultado, dia)


class BajaIn(Esquema):
    fecha_baja: date  # último día activo (D24)


@router.post("/usuarios/{usuario_id}/baja", response_model=CambioUsuarioOut)
def baja(
    usuario_id: int,
    datos: BajaIn,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    coordinador: Usuario = Depends(requiere_coordinador),
) -> CambioUsuarioOut:
    """Da de baja a un médico: sus horarios quedan sin titular y sus coberturas se reabren desde el día siguiente (D24)."""
    dia = hoy(reloj)
    resultado = dar_de_baja(db, usuario_id, datos.fecha_baja, coordinador, reloj)
    db.commit()
    return cambio_out(db, resultado, dia)

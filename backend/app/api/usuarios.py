from datetime import date, time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.esquemas import Esquema
from app.auth import requiere_coordinador
from app.db import get_db
from app.modelos import EstadoUsuario, RolUsuario, Usuario, VersionHorario
from app.reloj import Reloj, get_reloj, hoy
from app.repos.horarios import versiones_no_terminadas_por_medico
from app.repos.usuarios import listar_usuarios

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

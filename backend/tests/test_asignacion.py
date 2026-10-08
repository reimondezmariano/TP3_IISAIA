from datetime import date

from app.dominio.asignacion import CasoAsignacion, clasificar_asignacion, habilitado_para_turno
from app.modelos import EstadoUsuario, RolUsuario

TURNO = date(2026, 10, 20)
MEDICO, COORD = RolUsuario.MEDICO, RolUsuario.COORDINADOR
ACTIVO, PENDIENTE, BAJA = EstadoUsuario.ACTIVO, EstadoUsuario.PENDIENTE, EstadoUsuario.BAJA


def test_un_medico_activo_esta_habilitado():
    assert habilitado_para_turno(MEDICO, ACTIVO, None, TURNO) is True


def test_un_coordinador_nunca_esta_habilitado():
    assert habilitado_para_turno(COORD, ACTIVO, None, TURNO) is False


def test_un_pendiente_nunca_esta_habilitado():
    assert habilitado_para_turno(MEDICO, PENDIENTE, None, TURNO) is False


def test_baja_con_turno_en_su_ultimo_dia_esta_habilitado():
    assert habilitado_para_turno(MEDICO, BAJA, TURNO, TURNO) is True


def test_baja_con_turno_el_dia_siguiente_no_esta_habilitado():
    assert habilitado_para_turno(MEDICO, BAJA, date(2026, 10, 19), TURNO) is False


def test_baja_con_turno_antes_de_su_fecha_esta_habilitado():
    assert habilitado_para_turno(MEDICO, BAJA, date(2026, 11, 1), TURNO) is True


def test_baja_sin_fecha_no_esta_habilitado():
    assert habilitado_para_turno(MEDICO, BAJA, None, TURNO) is False


def test_los_tres_casos_de_asignacion():
    assert clasificar_asignacion(tiene_asignado=False, es_candidato=True) is CasoAsignacion.CANDIDATO_ELEGIDO
    assert clasificar_asignacion(tiene_asignado=False, es_candidato=False) is CasoAsignacion.ASIGNACION_DIRECTA
    assert clasificar_asignacion(tiene_asignado=True, es_candidato=False) is CasoAsignacion.REASIGNACION


def test_con_asignado_gana_la_reasignacion_aunque_sea_candidato():
    assert clasificar_asignacion(tiene_asignado=True, es_candidato=True) is CasoAsignacion.REASIGNACION

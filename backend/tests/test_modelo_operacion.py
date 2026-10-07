from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.modelos import (
    EstadoVacante,
    EventoTurno,
    Notificacion,
    Postulacion,
    TipoEventoTurno,
    Turno,
    Vacante,
    VersionHorario,
)
from app.repos.horarios import DatosVersion, crear_horario
from fabricas import crear_usuario, debe_fallar, guardar

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
SABADO = date(2026, 10, 17)
INICIO = datetime(2026, 10, 17, 8, tzinfo=ZONA)
FIN = datetime(2026, 10, 17, 20, tzinfo=ZONA)
AHORA = datetime(2026, 10, 12, 9, tzinfo=ZONA)


def nuevo_horario(sesion, medico):
    datos = DatosVersion(
        medico_id=medico.id,
        dia_semana=6,
        hora_inicio=time(8),
        duracion_horas=12,
        frecuencia_semanas=1,
        fecha_ancla=date(2026, 9, 7),
    )
    horario = crear_horario(sesion, datos, date(2026, 9, 7))
    version_id = sesion.scalar(select(VersionHorario.id).where(VersionHorario.horario_id == horario.id))
    return horario, version_id


def fila_turno(horario_id, version_id, titular_id, **cambios) -> Turno:
    datos = dict(
        horario_id=horario_id, fecha=SABADO, version_id=version_id, inicio=INICIO, fin=FIN, titular_id=titular_id
    )
    datos.update(cambios)
    return Turno(**datos)


def fila_vacante(turno, autor, **cambios) -> Vacante:
    datos = dict(turno_id=turno.id, generada_por_id=autor.id, motivo="Congreso", creada_en=AHORA)
    datos.update(cambios)
    return Vacante(**datos)


def fila_evento(turno, tipo=TipoEventoTurno.VACANTE_GENERADA, **cambios) -> EventoTurno:
    datos = dict(turno_id=turno.id, tipo=tipo, actor_id=None, ocurrido_en=AHORA)
    datos.update(cambios)
    return EventoTurno(**datos)


@pytest.fixture
def medico(sesion):
    return crear_usuario(sesion, "Florencia Lucca")


@pytest.fixture
def turno(sesion, medico):
    horario, version_id = nuevo_horario(sesion, medico)
    fila = fila_turno(horario.id, version_id, medico.id)
    guardar(sesion, fila)
    return fila


def test_migracion_crea_las_tablas_operativas_con_rls(sesion):
    filas = sesion.execute(
        text(
            "SELECT relname, relrowsecurity FROM pg_class WHERE relname IN "
            "('turno', 'vacante', 'postulacion', 'evento_turno', 'notificacion') ORDER BY relname"
        )
    ).all()
    assert filas == [
        ("evento_turno", True),
        ("notificacion", True),
        ("postulacion", True),
        ("turno", True),
        ("vacante", True),
    ]


def test_turno_guarda_el_snapshot_con_zona_horaria(sesion, turno, medico):
    sesion.expire_all()
    leido = sesion.get(Turno, turno.id)
    assert leido.inicio == INICIO
    assert leido.inicio.utcoffset() is not None
    assert leido.titular_id == medico.id
    assert (leido.asignado_id, leido.realizador_id, leido.consolidado_en, leido.sin_cobertura_en) == (
        None,
        None,
        None,
        None,
    )


def test_turno_unico_por_horario_y_fecha(sesion, turno):
    debe_fallar(sesion, fila_turno(turno.horario_id, turno.version_id, None), "ux_turno_horario_fecha")


def test_turno_rechaza_la_version_de_otro_horario(sesion, turno, medico):
    _, version_ajena = nuevo_horario(sesion, medico)
    fila = fila_turno(turno.horario_id, version_ajena, medico.id, fecha=date(2026, 10, 24))
    debe_fallar(sesion, fila, "fk_turno_version_del_horario")


def test_turno_rechaza_fin_que_no_es_posterior_al_inicio(sesion, turno):
    fila = fila_turno(turno.horario_id, turno.version_id, None, fecha=date(2026, 10, 24), fin=INICIO)
    debe_fallar(sesion, fila, "ck_turno_fin_posterior")


def test_realizador_solo_en_turno_consolidado(sesion, turno, medico):
    sin_consolidar = fila_turno(turno.horario_id, turno.version_id, None, fecha=date(2026, 10, 24), realizador_id=medico.id)
    debe_fallar(sesion, sin_consolidar, "ck_turno_realizador_consolidado")
    consolidado = fila_turno(
        turno.horario_id, turno.version_id, None, fecha=date(2026, 10, 31), realizador_id=medico.id, consolidado_en=FIN
    )
    guardar(sesion, consolidado)


def test_vacante_nace_abierta(sesion, turno, medico):
    vacante = fila_vacante(turno, medico)
    guardar(sesion, vacante)
    sesion.refresh(vacante)
    assert vacante.estado == EstadoVacante.ABIERTA
    assert vacante.cerrada_en is None


def test_una_sola_vacante_abierta_por_turno(sesion, turno, medico):
    guardar(sesion, fila_vacante(turno, medico))
    debe_fallar(sesion, fila_vacante(turno, medico), "ux_vacante_abierta_por_turno")


def test_se_abre_otra_vacante_cuando_las_anteriores_se_cerraron(sesion, turno, medico):
    guardar(sesion, fila_vacante(turno, medico, estado=EstadoVacante.RETIRADA, cerrada_en=AHORA))
    guardar(sesion, fila_vacante(turno, medico, estado=EstadoVacante.CUBIERTA, cerrada_en=AHORA))
    guardar(sesion, fila_vacante(turno, medico))


@pytest.mark.parametrize(
    "cambios",
    [
        dict(estado=EstadoVacante.ABIERTA, cerrada_en=AHORA),
        dict(estado=EstadoVacante.RETIRADA, cerrada_en=None),
        dict(estado=EstadoVacante.SIN_COBERTURA, cerrada_en=None),
    ],
)
def test_vacante_cerrada_si_y_solo_si_tiene_fecha_de_cierre(sesion, turno, medico, cambios):
    debe_fallar(sesion, fila_vacante(turno, medico, **cambios), "ck_vacante_cierre")


def test_postulacion_unica_por_turno_y_medico(sesion, turno):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    guardar(sesion, Postulacion(turno_id=turno.id, medico_id=carlos.id, creada_en=AHORA))
    debe_fallar(
        sesion, Postulacion(turno_id=turno.id, medico_id=carlos.id, creada_en=AHORA), "ux_postulacion_turno_medico"
    )


def test_evento_de_sistema_con_datos_vacios(sesion, turno):
    evento = fila_evento(turno)
    guardar(sesion, evento)
    sesion.refresh(evento)
    assert evento.actor_id is None
    assert evento.datos == {}


@pytest.mark.parametrize(
    "sentencia",
    ["UPDATE evento_turno SET actor_id = NULL WHERE id = :id", "DELETE FROM evento_turno WHERE id = :id"],
)
def test_bitacora_solo_admite_agregar(sesion, turno, medico, sentencia):
    evento = fila_evento(turno, actor_id=medico.id)
    guardar(sesion, evento)
    with pytest.raises(IntegrityError, match="solo admite agregar"):
        with sesion.begin_nested():
            sesion.execute(text(sentencia), {"id": evento.id})


def test_alerta_sin_cobertura_una_sola_vez_por_umbral(sesion, turno):
    alerta = TipoEventoTurno.ALERTA_SIN_COBERTURA
    guardar(sesion, fila_evento(turno, alerta, datos={"umbral": "48H"}))
    guardar(sesion, fila_evento(turno, alerta, datos={"umbral": "24H"}))
    debe_fallar(sesion, fila_evento(turno, alerta, datos={"umbral": "48H"}), "ux_evento_alerta_por_umbral")


def test_alerta_sin_umbral_es_rechazada(sesion, turno):
    debe_fallar(sesion, fila_evento(turno, TipoEventoTurno.ALERTA_SIN_COBERTURA), "ck_evento_alerta_umbral")


def test_otros_eventos_se_repiten_sin_limite(sesion, turno):
    guardar(sesion, fila_evento(turno, TipoEventoTurno.POSTULACION_CREADA))
    guardar(sesion, fila_evento(turno, TipoEventoTurno.POSTULACION_CREADA))


def test_notificacion_nace_sin_leer(sesion, turno, medico):
    notificacion = Notificacion(
        usuario_id=medico.id,
        tipo="VACANTE_URGENTE",
        mensaje="Vacante urgente el sábado 17/10 a las 08:00",
        turno_id=turno.id,
        creada_en=AHORA,
    )
    guardar(sesion, notificacion)
    sesion.refresh(notificacion)
    assert notificacion.leida_en is None
    assert notificacion.datos == {}


@pytest.mark.parametrize("umbral", ["", "48h", "12H", "inicio"])
def test_alerta_con_umbral_fuera_de_la_lista_es_rechazada(sesion, turno, umbral):
    """Solo "48H", "24H" e "INICIO": con variantes como "48h", el índice único dejaría repetir el aviso."""
    alerta = fila_evento(turno, TipoEventoTurno.ALERTA_SIN_COBERTURA, datos={"umbral": umbral})
    debe_fallar(sesion, alerta, "ck_evento_alerta_umbral")


def test_alerta_acepta_los_tres_umbrales(sesion, turno):
    for umbral in ("48H", "24H", "INICIO"):
        guardar(sesion, fila_evento(turno, TipoEventoTurno.ALERTA_SIN_COBERTURA, datos={"umbral": umbral}))

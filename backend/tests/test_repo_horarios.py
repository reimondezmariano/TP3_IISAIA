from datetime import date, time

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.dominio.calendario import Titular
from app.modelos import VersionHorario
from app.repos.horarios import DatosVersion, crear_horario, nueva_version, versiones_en_rango
from fabricas import crear_usuario


def datos(medico_id=None, dia=2, hora=time(7), dur=12, frec=1, ancla=date(2026, 9, 7)) -> DatosVersion:
    return DatosVersion(
        medico_id=medico_id,
        dia_semana=dia,
        hora_inicio=hora,
        duracion_horas=dur,
        frecuencia_semanas=frec,
        fecha_ancla=ancla,
    )


def test_crear_horario_crea_identidad_y_primera_version(sesion):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    horario = crear_horario(sesion, datos(medico_id=carlos.id), date(2026, 9, 7))
    [version] = sesion.scalars(select(VersionHorario).where(VersionHorario.horario_id == horario.id)).all()
    assert version.medico_id == carlos.id
    assert version.vigente_desde == date(2026, 9, 7)
    assert version.vigente_hasta is None


def test_nueva_version_cierra_la_vigente_y_abre_otra(sesion):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    horario = crear_horario(sesion, datos(medico_id=carlos.id), date(2026, 9, 7))
    nueva = nueva_version(sesion, horario.id, datos(medico_id=carlos.id, hora=time(8)), date(2026, 9, 28))
    versiones = sesion.scalars(
        select(VersionHorario).where(VersionHorario.horario_id == horario.id).order_by(VersionHorario.vigente_desde)
    ).all()
    assert [(v.vigente_desde, v.vigente_hasta, v.hora_inicio) for v in versiones] == [
        (date(2026, 9, 7), date(2026, 9, 28), time(7)),
        (date(2026, 9, 28), None, time(8)),
    ]
    assert nueva.id == versiones[1].id


def test_nueva_version_en_la_misma_fecha_de_inicio_la_rechaza_la_base(sesion):
    horario = crear_horario(sesion, datos(), date(2026, 9, 7))
    with pytest.raises(IntegrityError):
        with sesion.begin_nested():
            nueva_version(sesion, horario.id, datos(hora=time(9)), date(2026, 9, 7))


def test_versiones_en_rango_trae_titular_y_excluye_lo_que_no_toca(sesion):
    florencia = crear_usuario(sesion, "Florencia Lucca")
    vigente = crear_horario(sesion, datos(medico_id=florencia.id, dia=6), date(2026, 9, 7))
    crear_horario(sesion, datos(), date(2026, 9, 7), vigente_hasta=date(2026, 9, 28))
    crear_horario(sesion, datos(), date(2026, 11, 2))

    resultado = versiones_en_rango(sesion, date(2026, 10, 12), date(2026, 10, 18))

    assert [v.horario_id for v in resultado] == [vigente.id]
    assert resultado[0].titular == Titular(florencia.id, "Florencia Lucca")
    assert resultado[0].dia_semana == 6


def test_versiones_en_rango_incluye_la_que_termina_el_dia_de_desde(sesion):
    # Su último día es desde - 1, y un turno de ese día puede entrar en la ventana.
    horario = crear_horario(sesion, datos(dia=7, hora=time(20)), date(2026, 9, 7), vigente_hasta=date(2026, 10, 12))
    resultado = versiones_en_rango(sesion, date(2026, 10, 12), date(2026, 10, 12))
    assert [v.horario_id for v in resultado] == [horario.id]


def test_versiones_en_rango_sin_titular_devuelve_titular_none(sesion):
    crear_horario(sesion, datos(medico_id=None), date(2026, 9, 7))
    [version] = versiones_en_rango(sesion, date(2026, 10, 12), date(2026, 10, 18))
    assert version.titular is None


def test_nueva_version_en_medio_hereda_el_fin_de_la_que_parte(sesion):
    horario = crear_horario(sesion, datos(), date(2026, 9, 7))
    nueva_version(sesion, horario.id, datos(hora=time(9)), date(2026, 11, 2))
    nueva_version(sesion, horario.id, datos(hora=time(8)), date(2026, 10, 19))
    versiones = sesion.scalars(
        select(VersionHorario).where(VersionHorario.horario_id == horario.id).order_by(VersionHorario.vigente_desde)
    ).all()
    assert [(v.vigente_desde, v.vigente_hasta, v.hora_inicio) for v in versiones] == [
        (date(2026, 9, 7), date(2026, 10, 19), time(7)),
        (date(2026, 10, 19), date(2026, 11, 2), time(8)),
        (date(2026, 11, 2), None, time(9)),
    ]

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.dominio.calendario import (
    Titular,
    VersionPlantilla,
    calcular_turnos,
    formatear_id_turno,
    parsear_id_turno,
)
from app.errores import ErrorDominio

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
FLORENCIA = Titular(1, "Florencia Lucca")
MARIANO = Titular(2, "Mariano Reimondez")


def version(
    horario_id=1,
    version_id=None,
    dia=1,
    hora=time(8),
    dur=12,
    frec=1,
    ancla=date(2026, 9, 7),
    desde=date(2026, 9, 7),
    hasta=None,
    titular=FLORENCIA,
):
    return VersionPlantilla(
        version_id=version_id if version_id is not None else horario_id,
        horario_id=horario_id,
        titular=titular,
        dia_semana=dia,
        hora_inicio=hora,
        duracion_horas=dur,
        frecuencia_semanas=frec,
        fecha_ancla=ancla,
        vigente_desde=desde,
        vigente_hasta=hasta,
    )


def turnos(versiones, desde, hasta):
    return calcular_turnos(versiones, desde, hasta, ZONA)


def fechas(lista):
    return [t.fecha for t in lista]


def en_ba(*args):
    return datetime(*args, tzinfo=ZONA)


# Semanal

def test_horario_semanal_genera_un_turno_en_el_dia_correcto():
    [t] = turnos([version(dia=3)], date(2026, 10, 12), date(2026, 10, 18))
    assert t.id == "1:2026-10-14"
    assert t.fecha == date(2026, 10, 14)
    assert t.inicio == en_ba(2026, 10, 14, 8, 0)
    assert t.fin == en_ba(2026, 10, 14, 20, 0)
    assert t.duracion_horas == 12
    assert t.titular == FLORENCIA
    assert t.version_id == 1


def test_horario_semanal_genera_un_turno_por_semana():
    resultado = turnos([version(dia=3)], date(2026, 10, 12), date(2026, 11, 1))
    assert fechas(resultado) == [date(2026, 10, 14), date(2026, 10, 21), date(2026, 10, 28)]


# Semana por medio (D14)

def test_semana_por_medio_salta_las_semanas_que_no_cumplen_la_frecuencia():
    v = version(dia=4, frec=2, ancla=date(2026, 10, 12))
    resultado = turnos([v], date(2026, 10, 5), date(2026, 11, 8))
    assert fechas(resultado) == [date(2026, 10, 15), date(2026, 10, 29)]


def test_semana_por_medio_funciona_antes_de_la_fecha_ancla():
    v = version(dia=4, frec=2, ancla=date(2026, 10, 12))
    resultado = turnos([v], date(2026, 9, 21), date(2026, 10, 4))
    assert fechas(resultado) == [date(2026, 10, 1)]


def test_dos_horarios_quincenales_desfasados_alternan_el_mismo_hueco():
    martin = version(horario_id=5, dia=4, dur=24, frec=2, ancla=date(2026, 10, 12), titular=MARIANO)
    javier = version(horario_id=6, dia=4, dur=24, frec=2, ancla=date(2026, 10, 5))
    resultado = turnos([martin, javier], date(2026, 10, 5), date(2026, 10, 25))
    assert [(t.horario_id, t.fecha) for t in resultado if t.fecha.isoweekday() == 4] == [
        (6, date(2026, 10, 8)),
        (5, date(2026, 10, 15)),
        (6, date(2026, 10, 22)),
    ]


# Medianoche

def test_turno_que_cruza_la_medianoche_aparece_en_los_dos_dias():
    v = version(dia=1, hora=time(22), dur=8)
    [lunes] = turnos([v], date(2026, 10, 12), date(2026, 10, 12))
    [martes] = turnos([v], date(2026, 10, 13), date(2026, 10, 13))
    assert lunes.id == martes.id == "1:2026-10-12"
    assert lunes.fin == en_ba(2026, 10, 13, 6, 0)
    assert turnos([v], date(2026, 10, 14), date(2026, 10, 14)) == []


def test_turno_de_24_horas_aparece_en_los_dos_dias_que_toca():
    v = version(dia=1, hora=time(8), dur=24)
    assert fechas(turnos([v], date(2026, 10, 13), date(2026, 10, 13))) == [date(2026, 10, 12)]
    assert turnos([v], date(2026, 10, 12), date(2026, 10, 12))[0].fin == en_ba(2026, 10, 13, 8, 0)


def test_turno_que_termina_justo_a_las_00_de_desde_no_aparece():
    domingo = version(dia=7, hora=time(16), dur=8)
    assert turnos([domingo], date(2026, 10, 12), date(2026, 10, 12)) == []
    assert fechas(turnos([domingo], date(2026, 10, 11), date(2026, 10, 11))) == [date(2026, 10, 11)]


def test_turno_de_24_horas_desde_las_00_no_aparece_al_dia_siguiente():
    v = version(dia=1, hora=time(0), dur=24)
    assert turnos([v], date(2026, 10, 13), date(2026, 10, 13)) == []


# Superposición entre médicos

def test_horarios_superpuestos_de_distintos_medicos_generan_dos_turnos():
    a = version(horario_id=9, dia=3, hora=time(8), dur=12, titular=FLORENCIA)
    b = version(horario_id=10, dia=3, hora=time(14), dur=6, titular=MARIANO)
    resultado = turnos([b, a], date(2026, 10, 14), date(2026, 10, 14))
    assert [(t.horario_id, t.titular) for t in resultado] == [(9, FLORENCIA), (10, MARIANO)]


def test_mismo_inicio_se_ordena_por_horario():
    a = version(horario_id=3, dia=3)
    b = version(horario_id=2, dia=3, titular=MARIANO)
    resultado = turnos([a, b], date(2026, 10, 14), date(2026, 10, 14))
    assert [t.horario_id for t in resultado] == [2, 3]


# Cambio de versión

def test_cambio_de_version_usa_la_vieja_antes_y_la_nueva_despues():
    vieja = version(horario_id=7, version_id=1, dia=2, hora=time(7), hasta=date(2026, 9, 28))
    nueva = version(horario_id=7, version_id=2, dia=2, hora=time(8), desde=date(2026, 9, 28))
    resultado = turnos([vieja, nueva], date(2026, 9, 21), date(2026, 10, 4))
    assert [(t.id, t.inicio, t.version_id) for t in resultado] == [
        ("7:2026-09-22", en_ba(2026, 9, 22, 7, 0), 1),
        ("7:2026-09-29", en_ba(2026, 9, 29, 8, 0), 2),
    ]


def test_cambio_de_version_puede_cambiar_el_dia():
    vieja = version(horario_id=7, version_id=1, dia=2, hasta=date(2026, 9, 28))
    nueva = version(horario_id=7, version_id=2, dia=4, desde=date(2026, 9, 28))
    resultado = turnos([vieja, nueva], date(2026, 9, 21), date(2026, 10, 4))
    assert [t.id for t in resultado] == ["7:2026-09-22", "7:2026-10-01"]


def test_turno_que_empieza_antes_del_corte_y_termina_despues_pertenece_a_la_version_vieja():
    vieja = version(horario_id=4, version_id=1, dia=7, hora=time(20), hasta=date(2026, 10, 12))
    nueva = version(horario_id=4, version_id=2, dia=7, hora=time(8), desde=date(2026, 10, 12))
    [t] = turnos([vieja, nueva], date(2026, 10, 12), date(2026, 10, 12))
    assert t.version_id == 1
    assert t.fecha == date(2026, 10, 11)
    assert t.fin == en_ba(2026, 10, 12, 8, 0)


def test_el_dia_del_corte_pertenece_a_la_version_nueva():
    vieja = version(horario_id=7, version_id=1, dia=2, hora=time(7), hasta=date(2026, 9, 29))
    nueva = version(horario_id=7, version_id=2, dia=2, hora=time(8), desde=date(2026, 9, 29))
    [t] = turnos([vieja, nueva], date(2026, 9, 29), date(2026, 9, 29))
    assert (t.fecha, t.version_id, t.inicio) == (date(2026, 9, 29), 2, en_ba(2026, 9, 29, 8, 0))


def test_no_hay_turnos_antes_de_la_vigencia():
    v = version(dia=3, desde=date(2026, 10, 14))
    assert fechas(turnos([v], date(2026, 10, 5), date(2026, 10, 18))) == [date(2026, 10, 14)]


# Sin titular (D24)

def test_version_sin_titular_genera_turno_con_titular_none():
    [t] = turnos([version(dia=3, titular=None)], date(2026, 10, 14), date(2026, 10, 14))
    assert t.titular is None


# Identificador (D09)

def test_formatear_y_parsear_id_son_inversas():
    texto = formatear_id_turno(7, date(2026, 10, 17))
    assert texto == "7:2026-10-17"
    assert parsear_id_turno(texto) == (7, date(2026, 10, 17))


@pytest.mark.parametrize("texto", ["abc", "7-2026-10-10", "7:2026-13-01", "7:2026-10-1", ":2026-10-10", "x:2026-10-10", "7:2026-10-10\n", "٧:2026-10-10", "7:٢٠٢٦-10-10"])
def test_parsear_id_invalido_lanza_turno_id_invalido(texto):
    with pytest.raises(ErrorDominio) as error:
        parsear_id_turno(texto)
    assert error.value.codigo == "TURNO_ID_INVALIDO"
    assert error.value.status == 422

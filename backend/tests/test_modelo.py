from datetime import date, time

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DataError, IntegrityError

from app.modelos import EstadoUsuario, HorarioPactado, RolUsuario, Usuario, VersionHorario
from fabricas import crear_usuario


def nuevo_horario(sesion) -> HorarioPactado:
    horario = HorarioPactado()
    sesion.add(horario)
    sesion.flush()
    return horario


def fila_version(horario, **cambios) -> VersionHorario:
    datos = dict(
        horario_id=horario.id,
        medico_id=None,
        dia_semana=1,
        hora_inicio=time(8),
        duracion_horas=12,
        frecuencia_semanas=1,
        fecha_ancla=date(2026, 9, 7),
        vigente_desde=date(2026, 9, 7),
        vigente_hasta=None,
    )
    datos.update(cambios)
    return VersionHorario(**datos)


def guardar(sesion, objeto):
    sesion.add(objeto)
    sesion.flush()


def debe_fallar(sesion, objeto):
    # DataError: con vigente_hasta < vigente_desde, Postgres rechaza el daterange generado
    # ("range lower bound must be less than or equal to range upper bound") antes de evaluar los CHECK.
    with pytest.raises((IntegrityError, DataError)):
        with sesion.begin_nested():
            guardar(sesion, objeto)


def test_migracion_crea_las_tablas_con_rls(sesion):
    filas = sesion.execute(
        text(
            "SELECT relname, relrowsecurity FROM pg_class "
            "WHERE relname IN ('usuario', 'horario_pactado', 'version_horario') ORDER BY relname"
        )
    ).all()
    assert filas == [("horario_pactado", True), ("usuario", True), ("version_horario", True)]


def test_usuario_estado_por_defecto_es_pendiente(sesion):
    usuario = Usuario(nombre="Nuevo", email="nuevo@prueba.test", rol=RolUsuario.MEDICO)
    guardar(sesion, usuario)
    sesion.refresh(usuario)
    assert usuario.estado == EstadoUsuario.PENDIENTE


def test_email_unico_sin_distinguir_mayusculas(sesion):
    crear_usuario(sesion, "Florencia", email="Florencia@Prueba.test")
    debe_fallar(sesion, Usuario(nombre="Otra", email="florencia@prueba.TEST", rol=RolUsuario.MEDICO))


def test_exclusion_rechaza_vigencias_superpuestas_del_mismo_horario(sesion):
    horario = nuevo_horario(sesion)
    guardar(sesion, fila_version(horario, vigente_hasta=date(2026, 10, 12)))
    debe_fallar(sesion, fila_version(horario, vigente_desde=date(2026, 10, 5)))


def test_exclusion_rechaza_dos_versiones_abiertas_del_mismo_horario(sesion):
    horario = nuevo_horario(sesion)
    guardar(sesion, fila_version(horario))
    debe_fallar(sesion, fila_version(horario, vigente_desde=date(2026, 12, 7)))


def test_exclusion_acepta_vigencias_contiguas(sesion):
    horario = nuevo_horario(sesion)
    guardar(sesion, fila_version(horario, vigente_hasta=date(2026, 9, 28)))
    guardar(sesion, fila_version(horario, vigente_desde=date(2026, 9, 28)))
    cantidad = sesion.scalar(select(func.count()).where(VersionHorario.horario_id == horario.id))
    assert cantidad == 2


def test_horarios_distintos_pueden_superponerse(sesion):
    guardar(sesion, fila_version(nuevo_horario(sesion)))
    guardar(sesion, fila_version(nuevo_horario(sesion)))


def test_vigencia_generada_es_semiabierta(sesion):
    horario = nuevo_horario(sesion)
    version = fila_version(horario, vigente_hasta=date(2026, 9, 28))
    guardar(sesion, version)
    contiene = sesion.execute(
        text("SELECT vigencia @> date '2026-09-27', vigencia @> date '2026-09-28' FROM version_horario WHERE id = :id"),
        {"id": version.id},
    ).one()
    assert tuple(contiene) == (True, False)


@pytest.mark.parametrize(
    "cambios",
    [
        {"fecha_ancla": date(2026, 9, 8)},
        {"duracion_horas": 0},
        {"duracion_horas": 25},
        {"dia_semana": 0},
        {"dia_semana": 8},
        {"frecuencia_semanas": 0},
        {"vigente_hasta": date(2026, 9, 7)},
        {"vigente_hasta": date(2026, 9, 1)},
    ],
)
def test_checks_rechazan_valores_invalidos(sesion, cambios):
    debe_fallar(sesion, fila_version(nuevo_horario(sesion), **cambios))


def test_version_acepta_medico_vacio_y_medico_asignado(sesion):
    medico = crear_usuario(sesion, "Mariano")
    horario = nuevo_horario(sesion)
    guardar(sesion, fila_version(horario, medico_id=medico.id, vigente_hasta=date(2026, 10, 12)))
    guardar(sesion, fila_version(horario, medico_id=None, vigente_desde=date(2026, 10, 12)))
    assert [v.medico_id for v in sesion.scalars(select(VersionHorario).order_by(VersionHorario.vigente_desde))] == [
        medico.id,
        None,
    ]


@pytest.mark.commit_real
def test_commit_real_confirma_y_otra_sesion_lo_ve(fabrica_sesiones):
    with fabrica_sesiones() as primera:
        primera.add(Usuario(nombre="Confirmado", email="confirmado@prueba.test", rol=RolUsuario.MEDICO))
        primera.commit()
    with fabrica_sesiones() as segunda:
        assert segunda.scalar(select(func.count()).select_from(Usuario)) == 1


def test_despues_de_commit_real_la_base_queda_vacia(engine):
    # Corre después de la prueba anterior (orden del archivo): el fixture debe haber vaciado las tablas.
    with engine.connect() as conexion:
        assert conexion.execute(text("SELECT count(*) FROM usuario")).scalar_one() == 0

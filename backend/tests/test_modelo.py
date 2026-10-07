from datetime import date, time

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DataError

from app.modelos import EstadoUsuario, HorarioPactado, RolUsuario, Usuario, VersionHorario
from conftest import _vaciar_tablas
from fabricas import crear_usuario, debe_fallar, guardar


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
    debe_fallar(sesion, Usuario(nombre="Otra", email="florencia@prueba.TEST", rol=RolUsuario.MEDICO), "ux_usuario_email_lower")


def test_exclusion_rechaza_vigencias_superpuestas_del_mismo_horario(sesion):
    horario = nuevo_horario(sesion)
    guardar(sesion, fila_version(horario, vigente_hasta=date(2026, 10, 12)))
    debe_fallar(sesion, fila_version(horario, vigente_desde=date(2026, 10, 5)), "ex_version_horario_vigencia")


def test_exclusion_rechaza_dos_versiones_abiertas_del_mismo_horario(sesion):
    horario = nuevo_horario(sesion)
    guardar(sesion, fila_version(horario))
    debe_fallar(sesion, fila_version(horario, vigente_desde=date(2026, 12, 7)), "ex_version_horario_vigencia")


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
    "cambios, restriccion",
    [
        ({"fecha_ancla": date(2026, 9, 8)}, "ck_version_horario_ancla_lunes"),
        ({"duracion_horas": 0}, "ck_version_horario_duracion"),
        ({"duracion_horas": 25}, "ck_version_horario_duracion"),
        ({"dia_semana": 0}, "ck_version_horario_dia_semana"),
        ({"dia_semana": 8}, "ck_version_horario_dia_semana"),
        ({"frecuencia_semanas": 0}, "ck_version_horario_frecuencia"),
        ({"vigente_hasta": date(2026, 9, 7)}, "ck_version_horario_vigencia"),
    ],
)
def test_checks_rechazan_valores_invalidos(sesion, cambios, restriccion):
    debe_fallar(sesion, fila_version(nuevo_horario(sesion), **cambios), restriccion)


def test_vigencia_invertida_es_rechazada_por_el_rango_generado(sesion):
    # Postgres evalúa el daterange generado antes del CHECK: falla como DataError, sin nombre de restricción.
    with pytest.raises(DataError):
        with sesion.begin_nested():
            guardar(sesion, fila_version(nuevo_horario(sesion), vigente_hasta=date(2026, 9, 1)))


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


@pytest.mark.commit_real
def test_vaciar_tablas_borra_filas_y_reinicia_identidades(fabrica_sesiones, engine):
    with fabrica_sesiones() as sesion:
        sesion.add(Usuario(nombre="Uno", email="uno@prueba.test", rol=RolUsuario.MEDICO))
        sesion.commit()
    _vaciar_tablas(engine)
    with fabrica_sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(Usuario)) == 0
        nuevo = Usuario(nombre="Dos", email="dos@prueba.test", rol=RolUsuario.MEDICO)
        sesion.add(nuevo)
        sesion.commit()
        assert nuevo.id == 1


def test_baja_sin_fecha_es_rechazada(sesion):
    usuario = Usuario(nombre="Sin fecha", email="sinfecha@prueba.test", rol=RolUsuario.MEDICO, estado=EstadoUsuario.BAJA)
    debe_fallar(sesion, usuario, "ck_usuario_fecha_baja")


def test_fecha_de_baja_en_cuenta_activa_es_rechazada(sesion):
    usuario = Usuario(
        nombre="Activo",
        email="activo@prueba.test",
        rol=RolUsuario.MEDICO,
        estado=EstadoUsuario.ACTIVO,
        fecha_baja=date(2026, 10, 20),
    )
    debe_fallar(sesion, usuario, "ck_usuario_fecha_baja")

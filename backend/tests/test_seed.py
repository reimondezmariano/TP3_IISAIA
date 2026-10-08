import uuid
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.dominio.calendario import calcular_turnos
from app.modelos import (
    EstadoConsolidacion,
    EventoTurno,
    HorarioPactado,
    Notificacion,
    Postulacion,
    RolUsuario,
    TipoEventoTurno,
    Turno,
    Usuario,
    Vacante,
    VersionHorario,
)
from app.repos.horarios import versiones_en_rango
from fabricas import crear_usuario
from scripts.seed import cargar_datos_ejemplo, describir_destino, main

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


def contar(sesion, modelo):
    return sesion.scalar(select(func.count()).select_from(modelo))


def turnos_de(sesion, desde, hasta):
    return calcular_turnos(versiones_en_rango(sesion, desde, hasta), desde, hasta, ZONA)


def test_seed_dos_veces_deja_el_mismo_estado(sesion):
    cargar_datos_ejemplo(sesion)
    primera = [(u.id, u.nombre, u.email, u.rol) for u in sesion.scalars(select(Usuario).order_by(Usuario.id))]
    cargar_datos_ejemplo(sesion)
    segunda = [(u.id, u.nombre, u.email, u.rol) for u in sesion.scalars(select(Usuario).order_by(Usuario.id))]

    assert primera == segunda
    assert contar(sesion, Usuario) == 11
    assert contar(sesion, HorarioPactado) == 14
    assert contar(sesion, VersionHorario) == 15
    assert primera[0][1] == "Florencia Lucca"


def test_seed_tiene_un_coordinador_enzo_sin_horarios(sesion):
    cargar_datos_ejemplo(sesion)
    [enzo] = sesion.scalars(select(Usuario).where(Usuario.rol == RolUsuario.COORDINADOR)).all()
    assert enzo.nombre == "Enzo"
    assert sesion.scalar(select(func.count()).where(VersionHorario.medico_id == enzo.id)) == 0


def test_seed_cubre_la_semana_del_demo_day(sesion):
    cargar_datos_ejemplo(sesion)
    semana = turnos_de(sesion, date(2026, 10, 12), date(2026, 10, 18))

    nombres = {t.titular.nombre for t in semana if t.titular}
    assert {"Florencia Lucca", "Mariano Reimondez", "Carlos Lugones"} <= nombres
    assert len(nombres) == 9  # Javier hace semana por medio y no le toca la semana del 12/10

    assert {6, 8, 12, 24} <= {t.duracion_horas for t in semana}

    florencia_sabado = [
        t for t in semana if t.titular and t.titular.nombre == "Florencia Lucca" and t.fecha == date(2026, 10, 17)
    ]
    assert len(florencia_sabado) == 1

    assert any(t.fin.date() > t.inicio.date() for t in semana if t.fecha >= date(2026, 10, 12))

    jueves = {(t.titular.nombre, t.inicio.time()) for t in semana if t.fecha == date(2026, 10, 15)}
    assert ("Mariano Reimondez", time(14)) in jueves
    assert ("Martín Aguirre", time(8)) in jueves
    assert all(nombre != "Javier Torres" for nombre, _ in jueves)


def test_seed_semana_por_medio_alterna(sesion):
    cargar_datos_ejemplo(sesion)
    jueves_22 = {t.titular.nombre for t in turnos_de(sesion, date(2026, 10, 22), date(2026, 10, 22)) if t.fecha == date(2026, 10, 22)}
    assert "Javier Torres" in jueves_22
    assert "Mariano Reimondez" not in jueves_22
    assert "Martín Aguirre" not in jueves_22


def test_seed_carlos_cambio_de_hora_el_28_de_septiembre(sesion):
    cargar_datos_ejemplo(sesion)

    def martes_de_carlos(dia):
        return [
            t.inicio.time()
            for t in turnos_de(sesion, dia, dia)
            if t.titular and t.titular.nombre == "Carlos Lugones" and t.fecha == dia
        ]

    assert martes_de_carlos(date(2026, 9, 15)) == [time(7)]
    assert martes_de_carlos(date(2026, 10, 13)) == [time(8)]


def test_main_sin_confirmar_no_modifica_nada(capsys):
    assert main([]) == 0
    salida = capsys.readouterr().out
    assert "--confirmar" in salida


def test_describir_destino_omite_el_puerto_si_no_esta():
    assert describir_destino("postgresql://u:p@db.ejemplo.com/postgres") == "db.ejemplo.com/postgres"
    assert describir_destino("postgresql://u:p@localhost:5433/guardia") == "localhost:5433/guardia"


def test_seed_vacia_las_tablas_operativas(sesion):
    cargar_datos_ejemplo(sesion)
    medico = sesion.scalars(select(Usuario).order_by(Usuario.id)).first()
    version = sesion.scalars(select(VersionHorario).order_by(VersionHorario.id)).first()
    turno = Turno(
        horario_id=version.horario_id,
        fecha=date(2026, 10, 17),
        version_id=version.id,
        inicio=datetime(2026, 10, 17, 8, tzinfo=ZONA),
        fin=datetime(2026, 10, 17, 20, tzinfo=ZONA),
        titular_id=medico.id,
    )
    sesion.add(turno)
    sesion.flush()
    ahora = datetime(2026, 10, 12, 9, tzinfo=ZONA)
    sesion.add_all(
        [
            Vacante(turno_id=turno.id, generada_por_id=medico.id, creada_en=ahora),
            Postulacion(turno_id=turno.id, medico_id=medico.id, creada_en=ahora),
            EventoTurno(turno_id=turno.id, tipo=TipoEventoTurno.VACANTE_GENERADA, ocurrido_en=ahora),
            Notificacion(usuario_id=medico.id, tipo="PRUEBA", mensaje="x", creada_en=ahora),
        ]
    )
    sesion.flush()
    # La recarga reutiliza los ids (RESTART IDENTITY): soltar los objetos de la carga anterior.
    # Desde la tarea 6, el seed lo hace por su cuenta.
    sesion.expunge_all()

    cargar_datos_ejemplo(sesion)

    for modelo in (Turno, Vacante, Postulacion, EventoTurno, Notificacion):
        assert contar(sesion, modelo) == 0


def coordinador(sesion) -> Usuario:
    return sesion.scalar(select(Usuario).where(Usuario.rol == RolUsuario.COORDINADOR))


def test_seed_conserva_los_vinculos_con_supabase(sesion):
    cargar_datos_ejemplo(sesion)
    enzo = coordinador(sesion)
    cuenta = uuid.uuid4()
    enzo.auth_id = cuenta
    enzo.email = enzo.email.upper()  # el vínculo se busca sin distinguir mayúsculas
    sesion.flush()

    conservados = cargar_datos_ejemplo(sesion)

    assert conservados == 1
    enzo = coordinador(sesion)
    assert enzo.auth_id == cuenta
    assert enzo.email == "enzo@guardiaviva.test"
    con_cuenta = sesion.scalar(select(func.count()).select_from(Usuario).where(Usuario.auth_id.is_not(None)))
    assert con_cuenta == 1


def test_seed_sin_vinculos_previos_no_vincula_nada(sesion):
    assert cargar_datos_ejemplo(sesion) == 0
    assert sesion.scalar(select(func.count()).select_from(Usuario).where(Usuario.auth_id.is_not(None))) == 0


def test_seed_borra_usuarios_que_no_son_de_ejemplo_aunque_tengan_cuenta(sesion):
    cargar_datos_ejemplo(sesion)
    crear_usuario(sesion, "Registrada desde la app", email="nueva@prueba.test")

    assert cargar_datos_ejemplo(sesion) == 0
    assert sesion.scalar(select(func.count()).select_from(Usuario)) == 11


def test_seed_vacia_la_marca_de_consolidacion(sesion):
    # Review Focus 1: con la marca vieja, después de reiniciar la demo no se consolidaría la historia.
    sesion.add(EstadoConsolidacion(id=1, consolidado_hasta=date(2026, 12, 1)))
    sesion.flush()
    cargar_datos_ejemplo(sesion)
    assert sesion.scalar(select(func.count()).select_from(EstadoConsolidacion)) == 0

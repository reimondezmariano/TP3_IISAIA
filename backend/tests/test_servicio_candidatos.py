from datetime import date, time, timedelta

import pytest
from sqlalchemy import func, select, update

from app.dominio.elegibilidad import Motivo
from app.errores import ErrorDominio
from app.modelos import EstadoUsuario, Postulacion, RolUsuario, Turno, Usuario
from app.servicios.asignacion import asignar
from app.servicios.postulaciones import listar_candidatos, postular, retirar_postulacion
from app.servicios.vacantes import generar_vacante
from fabricas import ZONA, crear_horario_de_prueba, crear_usuario, guardar_turno

# Reloj de prueba: lunes 12/10/2026 09:00. El turno evaluado es el martes 20/10 08:00 a 20:00 (octubre).
FECHA = "2026-10-20"


@pytest.fixture
def turno(sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos")
    horario = crear_horario_de_prueba(sesion, carlos.id)
    turno_id = f"{horario.id}:{FECHA}"
    generar_vacante(sesion, turno_id, carlos, None, reloj, ZONA)
    return turno_id


def postulados(sesion, reloj, turno_id, *nombres):
    """Crea y postula a los médicos, de a uno por minuto, en el orden dado."""
    medicos = []
    for nombre in nombres:
        medico = crear_usuario(sesion, nombre)
        postular(sesion, turno_id, medico, reloj, ZONA)
        reloj.avanzar(timedelta(minutes=1))
        medicos.append(medico)
    return medicos


def coberturas(sesion, medico, *dias):
    """Turnos de octubre en que `medico` quedó asignado sin ser el titular (miércoles, sin tocar el turno evaluado)."""
    otro = crear_usuario(sesion, f"Titular de {medico.nombre}")
    horario = crear_horario_de_prueba(sesion, otro.id, dia=3)
    for dia in dias:
        guardar_turno(sesion, horario.id, date(2026, 10, dia), asignado_id=medico.id)


def nombres(resultado):
    return [c.medico.nombre for c in resultado.candidatos]


def test_ordena_por_menos_coberturas_en_el_mes_del_turno(sesion, reloj, turno):
    ana, beto, cleo = postulados(sesion, reloj, turno, "Ana", "Beto", "Cleo")
    coberturas(sesion, ana, 7, 14)
    coberturas(sesion, cleo, 28)

    resultado = listar_candidatos(sesion, turno, ZONA)

    assert nombres(resultado) == ["Beto", "Cleo", "Ana"]
    assert [(c.posicion, c.coberturas_mes) for c in resultado.candidatos] == [(1, 0), (2, 1), (3, 2)]
    assert resultado.mes == "2026-10"


def test_las_coberturas_de_otro_mes_no_cuentan(sesion, reloj, turno):
    ana, beto = postulados(sesion, reloj, turno, "Ana", "Beto")
    otro = crear_usuario(sesion, "Titular")
    horario = crear_horario_de_prueba(sesion, otro.id, dia=3)
    guardar_turno(sesion, horario.id, date(2026, 9, 30), asignado_id=ana.id)  # septiembre
    guardar_turno(sesion, horario.id, date(2026, 11, 4), asignado_id=ana.id)  # noviembre

    resultado = listar_candidatos(sesion, turno, ZONA)

    assert nombres(resultado) == ["Ana", "Beto"]  # empate en 0: gana quien se postuló antes
    assert [c.coberturas_mes for c in resultado.candidatos] == [0, 0]


def test_desempata_por_hora_de_postulacion(sesion, reloj, turno):
    postulados(sesion, reloj, turno, "Primero", "Segundo", "Tercero")
    assert nombres(listar_candidatos(sesion, turno, ZONA)) == ["Primero", "Segundo", "Tercero"]


def test_las_horas_de_la_semana_son_informativas_y_no_cambian_el_orden(sesion, reloj, turno):
    ana, beto = postulados(sesion, reloj, turno, "Ana", "Beto")
    crear_horario_de_prueba(sesion, ana.id, dia=3)  # Ana ya hace el miércoles 21/10 de 12 h

    resultado = listar_candidatos(sesion, turno, ZONA)

    assert nombres(resultado) == ["Ana", "Beto"]
    assert [c.horas_semana for c in resultado.candidatos] == [12.0, 0.0]


def test_los_no_elegibles_van_al_final_con_su_motivo(sesion, reloj, turno):
    ana, beto, cleo = postulados(sesion, reloj, turno, "Ana", "Beto", "Cleo")
    ocupada = crear_horario_de_prueba(sesion, None, hora=time(10), dur=4)  # martes 10:00 a 14:00
    guardar_turno(sesion, ocupada.id, date(2026, 10, 20), asignado_id=ana.id)  # el impedimento aparece después

    resultado = listar_candidatos(sesion, turno, ZONA)

    assert nombres(resultado) == ["Beto", "Cleo", "Ana"]
    ana_calculada = resultado.candidatos[-1]
    assert (ana_calculada.posicion, ana_calculada.elegible, ana_calculada.motivo) == (None, False, Motivo.GUARDIA_SUPERPUESTA)
    assert [c.posicion for c in resultado.candidatos[:2]] == [1, 2]


def test_un_impedimento_que_desaparece_vuelve_elegible(sesion, reloj, turno):
    [ana] = postulados(sesion, reloj, turno, "Ana")
    ocupada = crear_horario_de_prueba(sesion, None, hora=time(10), dur=4)
    ocupado = guardar_turno(sesion, ocupada.id, date(2026, 10, 20), asignado_id=ana.id)
    assert listar_candidatos(sesion, turno, ZONA).candidatos[0].elegible is False

    sesion.execute(update(Turno).where(Turno.id == ocupado.id).values(asignado_id=None))
    sesion.expire_all()

    candidata = listar_candidatos(sesion, turno, ZONA).candidatos[0]
    assert (candidata.elegible, candidata.posicion, candidata.motivo) == (True, 1, None)


def test_no_lista_postulaciones_retiradas(sesion, reloj, turno):
    ana, beto = postulados(sesion, reloj, turno, "Ana", "Beto")
    de_ana = sesion.scalar(select(Postulacion).where(Postulacion.medico_id == ana.id))
    retirar_postulacion(sesion, de_ana.id, ana, reloj)

    assert nombres(listar_candidatos(sesion, turno, ZONA)) == ["Beto"]


def test_no_lista_a_un_medico_dado_de_baja_para_un_turno_posterior_a_su_baja(sesion, reloj, turno):
    ana, beto, cleo = postulados(sesion, reloj, turno, "Ana", "Beto", "Cleo")
    sesion.execute(update(Usuario).where(Usuario.id == ana.id).values(estado=EstadoUsuario.BAJA, fecha_baja=date(2026, 10, 19)))
    sesion.execute(update(Usuario).where(Usuario.id == beto.id).values(estado=EstadoUsuario.BAJA, fecha_baja=date(2026, 10, 20)))
    sesion.expire_all()

    assert nombres(listar_candidatos(sesion, turno, ZONA)) == ["Beto", "Cleo"]  # Beto cubre hasta su último día


def test_un_turno_sin_postulantes_devuelve_lista_vacia(sesion, reloj, turno):
    assert listar_candidatos(sesion, turno, ZONA).candidatos == []


def test_un_turno_que_nunca_se_guardo_devuelve_lista_vacia_con_su_mes(sesion):
    horario = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos").id)
    resultado = listar_candidatos(sesion, f"{horario.id}:2026-10-27", ZONA)
    assert (resultado.candidatos, resultado.mes) == ([], "2026-10")
    assert sesion.scalar(select(func.count()).select_from(Turno)) == 0


def test_turno_inexistente_responde_404(sesion):
    horario = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos").id)
    with pytest.raises(ErrorDominio) as error:
        listar_candidatos(sesion, f"{horario.id}:2026-10-21", ZONA)  # miércoles
    assert (error.value.codigo, error.value.status) == ("TURNO_NO_ENCONTRADO", 404)


def coordinador(sesion):
    return crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)


def test_el_asignado_actual_no_aparece_como_candidato(sesion, reloj, turno):
    ana, beto = postulados(sesion, reloj, turno, "Ana", "Beto")
    asignar(sesion, turno, ana.id, False, coordinador(sesion), reloj, ZONA)

    assert nombres(listar_candidatos(sesion, turno, ZONA)) == ["Beto"]  # Ana ya está asignada: no se la puede elegir


def test_quien_cancelo_no_vuelve_a_aparecer_como_candidato(sesion, reloj, turno):
    ana, beto = postulados(sesion, reloj, turno, "Ana", "Beto")
    asignar(sesion, turno, ana.id, False, coordinador(sesion), reloj, ZONA)
    generar_vacante(sesion, turno, ana, "Ya no puedo", reloj, ZONA)  # Ana cancela y se abre otra vacante

    resultado = listar_candidatos(sesion, turno, ZONA)

    assert nombres(resultado) == ["Beto"]  # D16: los demás siguen como reserva; Ana ya dijo que no puede
    assert [c.posicion for c in resultado.candidatos] == [1]


def test_una_fecha_en_el_extremo_del_calendario_responde_404_y_no_desborda(sesion):
    for extremo in ("1:0001-01-01", "1:9999-12-31"):
        with pytest.raises(ErrorDominio) as error:
            listar_candidatos(sesion, extremo, ZONA)
        assert (error.value.codigo, error.value.status) == ("TURNO_NO_ENCONTRADO", 404)

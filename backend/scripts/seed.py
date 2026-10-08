"""Datos de ejemplo para desarrollo y demo (docs/guion-demo.md, "Datos de ejemplo necesarios").

Vacía las tablas y vuelve a cargar todo: correrlo dos veces deja el mismo estado y los mismos ids.
Conserva los vínculos con Supabase Auth de los usuarios de ejemplo (por email); los demás usuarios se borran.
Uso, desde backend/: python -m scripts.seed --confirmar
F2 a F4 suman acá la historia, las vacantes y el turno de la vacante urgente.
"""

import argparse
import uuid
from dataclasses import replace
from datetime import date, time

from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modelos import EstadoUsuario, RolUsuario, Usuario
from app.repos.horarios import DatosVersion, crear_horario, nueva_version

DOMINIO_EMAIL = "guardiaviva.test"
INICIO_VIGENCIAS = date(2026, 9, 7)  # lunes; deja lugar a dos semanas de historia antes del Demo Day (F4)
ANCLA_SEMANA_DEMO = date(2026, 10, 12)  # lunes de la semana del Demo Day
ANCLA_SEMANA_PREVIA = date(2026, 10, 5)

MEDICOS = [
    ("Florencia Lucca", "florencia.lucca"),
    ("Mariano Reimondez", "mariano.reimondez"),
    ("Carlos Lugones", "carlos.lugones"),
    ("Valentina Ríos", "valentina.rios"),
    ("Martín Aguirre", "martin.aguirre"),
    ("Lucía Fernández", "lucia.fernandez"),
    ("Diego Sosa", "diego.sosa"),
    ("Paula Méndez", "paula.mendez"),
    ("Javier Torres", "javier.torres"),
    ("Sofía Romero", "sofia.romero"),
]
COORDINADOR = ("Enzo", "enzo")

# (titular, día ISO, inicio, duración en horas, frecuencia en semanas, fecha ancla). El orden fija los ids 1 a 14.
HORARIOS = [
    ("florencia.lucca", 6, time(8), 12, 1, INICIO_VIGENCIAS),  # 1: sábado 17/10
    ("florencia.lucca", 3, time(20), 12, 1, INICIO_VIGENCIAS),  # 2: cruza la medianoche
    ("mariano.reimondez", 1, time(8), 24, 1, INICIO_VIGENCIAS),  # 3: 24 h
    ("mariano.reimondez", 4, time(14), 8, 2, ANCLA_SEMANA_DEMO),  # 4: semana por medio
    ("martin.aguirre", 4, time(8), 24, 2, ANCLA_SEMANA_DEMO),  # 5: alterna con Javier (D14)
    ("javier.torres", 4, time(8), 24, 2, ANCLA_SEMANA_PREVIA),  # 6
    ("carlos.lugones", 2, time(7), 12, 1, INICIO_VIGENCIAS),  # 7: pasa a las 08:00 el 28/9
    ("carlos.lugones", 5, time(20), 12, 1, INICIO_VIGENCIAS),  # 8: cruza la medianoche
    ("valentina.rios", 3, time(8), 12, 1, INICIO_VIGENCIAS),  # 9: se superpone con Sofía
    ("sofia.romero", 3, time(14), 6, 1, INICIO_VIGENCIAS),  # 10: 6 h
    ("lucia.fernandez", 7, time(8), 24, 1, INICIO_VIGENCIAS),  # 11: 24 h
    ("diego.sosa", 6, time(20), 12, 1, INICIO_VIGENCIAS),  # 12: sábado a domingo
    ("paula.mendez", 2, time(20), 12, 1, INICIO_VIGENCIAS),  # 13: cruza la medianoche
    ("paula.mendez", 5, time(8), 12, 1, INICIO_VIGENCIAS),  # 14
]
HORARIO_CON_CAMBIO = 7
FECHA_CAMBIO = date(2026, 9, 28)
NUEVA_HORA = time(8)


def _email(usuario: str) -> str:
    return f"{usuario}@{DOMINIO_EMAIL}"


def _vinculos_con_supabase(sesion: Session) -> dict[str, uuid.UUID]:
    """Cuentas de Supabase Auth ya vinculadas, por email en minúsculas (D06, D28)."""
    filas = sesion.execute(
        select(func.lower(Usuario.email), Usuario.auth_id).where(Usuario.auth_id.is_not(None))
    ).all()
    return {email: auth_id for email, auth_id in filas}


def cargar_datos_ejemplo(sesion: Session) -> int:
    """Vacía las tablas y carga usuarios y horarios. No hace commit.

    Cada usuario de ejemplo recupera la cuenta de Supabase Auth que tenía el usuario con su mismo email,
    así nadie tiene que volver a registrarse después de reiniciar la demo. Devuelve cuántas conservó.
    """
    vinculos = _vinculos_con_supabase(sesion)
    sesion.execute(
        text("TRUNCATE usuario, horario_pactado, version_horario, consolidacion_estado RESTART IDENTITY CASCADE")
    )
    # RESTART IDENTITY reutiliza los ids: los objetos de la carga anterior no deben chocar con los nuevos.
    sesion.expunge_all()

    def nuevo_usuario(nombre: str, usuario: str, rol: RolUsuario) -> Usuario:
        email = _email(usuario)
        fila = Usuario(
            nombre=nombre,
            email=email,
            rol=rol,
            estado=EstadoUsuario.ACTIVO,
            auth_id=vinculos.get(email.lower()),
        )
        sesion.add(fila)
        sesion.flush()
        return fila

    ids: dict[str, int] = {}
    for nombre, usuario in MEDICOS:
        ids[usuario] = nuevo_usuario(nombre, usuario, RolUsuario.MEDICO).id
    nombre, usuario = COORDINADOR
    nuevo_usuario(nombre, usuario, RolUsuario.COORDINADOR)
    conservados = sum(1 for _, usuario in [*MEDICOS, COORDINADOR] if _email(usuario).lower() in vinculos)

    for titular, dia, inicio, duracion, frecuencia, ancla in HORARIOS:
        datos = DatosVersion(
            medico_id=ids[titular],
            dia_semana=dia,
            hora_inicio=inicio,
            duracion_horas=duracion,
            frecuencia_semanas=frecuencia,
            fecha_ancla=ancla,
        )
        horario = crear_horario(sesion, datos, INICIO_VIGENCIAS)
        if horario.id == HORARIO_CON_CAMBIO:
            nueva_version(sesion, horario.id, replace(datos, hora_inicio=NUEVA_HORA), FECHA_CAMBIO)

    return conservados


def describir_destino(url: str) -> str:
    destino = make_url(url)
    puerto = f":{destino.port}" if destino.port is not None else ""
    return f"{destino.host}{puerto}/{destino.database}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Carga los datos de ejemplo de Guardia Viva (borra los datos actuales).")
    parser.add_argument("--confirmar", action="store_true", help="confirma que se borran los datos actuales")
    args = parser.parse_args(argv)

    print(f"Base de destino: {describir_destino(get_settings().database_url)}")
    if not args.confirmar:
        print("No se modificó nada. Volvé a correrlo con --confirmar para borrar y recargar los datos.")
        return 0

    from app.db import SessionLocal

    with SessionLocal() as sesion, sesion.begin():
        conservados = cargar_datos_ejemplo(sesion)
    print(f"Datos de ejemplo cargados: {len(MEDICOS)} médicos, 1 coordinador, {len(HORARIOS)} horarios.")
    print(f"Cuentas de Supabase conservadas: {conservados}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

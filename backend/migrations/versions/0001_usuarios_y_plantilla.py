"""Usuarios y plantilla de horarios pactados (D08, D10, D23, D24, D07)

Revision ID: 0001
Revises:
Create Date: 2026-10-05
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_UPGRADE = [
    "CREATE EXTENSION IF NOT EXISTS btree_gist",
    "CREATE TYPE rol_usuario AS ENUM ('MEDICO', 'COORDINADOR')",
    "CREATE TYPE estado_usuario AS ENUM ('PENDIENTE', 'ACTIVO', 'BAJA')",
    """
    CREATE TABLE usuario (
        id serial PRIMARY KEY,
        nombre text NOT NULL,
        email text NOT NULL,
        rol rol_usuario NOT NULL,
        estado estado_usuario NOT NULL DEFAULT 'PENDIENTE',
        fecha_baja date,
        auth_id uuid UNIQUE,
        creado_en timestamptz NOT NULL DEFAULT now()
    )
    """,
    "CREATE UNIQUE INDEX ux_usuario_email_lower ON usuario (lower(email))",
    """
    CREATE TABLE horario_pactado (
        id serial PRIMARY KEY,
        creado_en timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE version_horario (
        id serial PRIMARY KEY,
        horario_id integer NOT NULL REFERENCES horario_pactado (id),
        medico_id integer REFERENCES usuario (id),
        dia_semana smallint NOT NULL,
        hora_inicio time NOT NULL,
        duracion_horas smallint NOT NULL,
        frecuencia_semanas smallint NOT NULL,
        fecha_ancla date NOT NULL,
        vigente_desde date NOT NULL,
        vigente_hasta date,
        vigencia daterange GENERATED ALWAYS AS (daterange(vigente_desde, vigente_hasta, '[)')) STORED,
        CONSTRAINT ck_version_horario_dia_semana CHECK (dia_semana BETWEEN 1 AND 7),
        CONSTRAINT ck_version_horario_duracion CHECK (duracion_horas BETWEEN 1 AND 24),
        CONSTRAINT ck_version_horario_frecuencia CHECK (frecuencia_semanas >= 1),
        CONSTRAINT ck_version_horario_ancla_lunes CHECK (extract(isodow FROM fecha_ancla) = 1),
        CONSTRAINT ck_version_horario_vigencia CHECK (vigente_hasta IS NULL OR vigente_hasta > vigente_desde),
        CONSTRAINT ex_version_horario_vigencia EXCLUDE USING gist (horario_id WITH =, vigencia WITH &&)
    )
    """,
    "CREATE INDEX ix_version_horario_medico ON version_horario (medico_id)",
    # D07: RLS activado sin políticas; el backend se conecta como dueño de las tablas.
    "ALTER TABLE usuario ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE horario_pactado ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE version_horario ENABLE ROW LEVEL SECURITY",
]

_DOWNGRADE = [
    "DROP TABLE version_horario",
    "DROP TABLE horario_pactado",
    "DROP TABLE usuario",
    "DROP TYPE estado_usuario",
    "DROP TYPE rol_usuario",
]


def upgrade() -> None:
    for sentencia in _UPGRADE:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _DOWNGRADE:
        op.execute(sentencia)

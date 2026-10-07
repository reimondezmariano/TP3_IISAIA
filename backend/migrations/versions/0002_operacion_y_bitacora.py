"""Turno materializado, vacantes, postulaciones, bitácora y notificaciones (D08, D11, D15, D16, D19 a D22, D25, D07)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_UPGRADE = [
    "CREATE TYPE estado_vacante AS ENUM ('ABIERTA', 'RETIRADA', 'CUBIERTA', 'SIN_COBERTURA')",
    """
    CREATE TYPE tipo_evento_turno AS ENUM (
        'VACANTE_GENERADA', 'VACANTE_RETIRADA', 'POSTULACION_CREADA', 'POSTULACION_RETIRADA',
        'CANDIDATO_ELEGIDO', 'ASIGNACION_DIRECTA', 'REASIGNACION', 'TURNO_SIN_COBERTURA',
        'REALIZADOR_RECTIFICADO', 'ALERTA_SIN_COBERTURA'
    )
    """,
    # Destino de la FK compuesta del turno: la versión tiene que ser del mismo horario.
    "ALTER TABLE version_horario ADD CONSTRAINT ux_version_horario_id_horario UNIQUE (id, horario_id)",
    """
    CREATE TABLE turno (
        id serial PRIMARY KEY,
        horario_id integer NOT NULL REFERENCES horario_pactado (id),
        fecha date NOT NULL,
        version_id integer NOT NULL,
        inicio timestamptz NOT NULL,
        fin timestamptz NOT NULL,
        titular_id integer REFERENCES usuario (id),
        asignado_id integer REFERENCES usuario (id),
        realizador_id integer REFERENCES usuario (id),
        sin_cobertura_en timestamptz,
        consolidado_en timestamptz,
        creado_en timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT ux_turno_horario_fecha UNIQUE (horario_id, fecha),
        CONSTRAINT fk_turno_version_del_horario FOREIGN KEY (version_id, horario_id)
            REFERENCES version_horario (id, horario_id),
        CONSTRAINT ck_turno_fin_posterior CHECK (fin > inicio),
        CONSTRAINT ck_turno_realizador_consolidado CHECK (realizador_id IS NULL OR consolidado_en IS NOT NULL)
    )
    """,
    "CREATE INDEX ix_turno_inicio ON turno (inicio)",
    "CREATE INDEX ix_turno_asignado ON turno (asignado_id)",
    """
    CREATE TABLE vacante (
        id serial PRIMARY KEY,
        turno_id integer NOT NULL REFERENCES turno (id),
        generada_por_id integer NOT NULL REFERENCES usuario (id),
        motivo text,
        estado estado_vacante NOT NULL DEFAULT 'ABIERTA',
        creada_en timestamptz NOT NULL,
        cerrada_en timestamptz,
        CONSTRAINT ck_vacante_cierre CHECK ((estado = 'ABIERTA') = (cerrada_en IS NULL))
    )
    """,
    # D15: como máximo una vacante abierta por turno.
    "CREATE UNIQUE INDEX ux_vacante_abierta_por_turno ON vacante (turno_id) WHERE estado = 'ABIERTA'",
    """
    CREATE TABLE postulacion (
        id serial PRIMARY KEY,
        turno_id integer NOT NULL REFERENCES turno (id),
        medico_id integer NOT NULL REFERENCES usuario (id),
        creada_en timestamptz NOT NULL,
        retirada_en timestamptz,
        CONSTRAINT ux_postulacion_turno_medico UNIQUE (turno_id, medico_id)
    )
    """,
    "CREATE INDEX ix_postulacion_medico ON postulacion (medico_id)",
    """
    CREATE TABLE evento_turno (
        id serial PRIMARY KEY,
        turno_id integer NOT NULL REFERENCES turno (id),
        tipo tipo_evento_turno NOT NULL,
        actor_id integer REFERENCES usuario (id),
        ocurrido_en timestamptz NOT NULL,
        datos jsonb NOT NULL DEFAULT '{}'::jsonb,
        CONSTRAINT ck_evento_alerta_umbral CHECK (
            tipo <> 'ALERTA_SIN_COBERTURA' OR coalesce(datos->>'umbral', '') IN ('48H', '24H', 'INICIO')
        )
    )
    """,
    "CREATE INDEX ix_evento_turno_turno ON evento_turno (turno_id, ocurrido_en)",
    # D19: cada alerta escalonada se emite una sola vez por turno y umbral.
    """
    CREATE UNIQUE INDEX ux_evento_alerta_por_umbral ON evento_turno (turno_id, (datos->>'umbral'))
        WHERE tipo = 'ALERTA_SIN_COBERTURA'
    """,
    # D22: la bitácora solo se agrega. TRUNCATE (seed y pruebas) no dispara triggers de fila.
    """
    CREATE FUNCTION evento_turno_solo_agregar() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION 'La bitácora (evento_turno) solo admite agregar filas' USING ERRCODE = 'restrict_violation';
    END
    $$
    """,
    """
    CREATE TRIGGER tg_evento_turno_solo_agregar BEFORE UPDATE OR DELETE ON evento_turno
        FOR EACH ROW EXECUTE FUNCTION evento_turno_solo_agregar()
    """,
    """
    CREATE TABLE notificacion (
        id serial PRIMARY KEY,
        usuario_id integer NOT NULL REFERENCES usuario (id),
        tipo text NOT NULL,
        mensaje text NOT NULL,
        turno_id integer REFERENCES turno (id),
        datos jsonb NOT NULL DEFAULT '{}'::jsonb,
        creada_en timestamptz NOT NULL,
        leida_en timestamptz
    )
    """,
    "CREATE INDEX ix_notificacion_usuario ON notificacion (usuario_id, creada_en)",
    # D07: RLS activado sin políticas.
    "ALTER TABLE turno ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE vacante ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE postulacion ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE evento_turno ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE notificacion ENABLE ROW LEVEL SECURITY",
]

_DOWNGRADE = [
    "DROP TABLE notificacion",
    "DROP TABLE evento_turno",
    "DROP FUNCTION evento_turno_solo_agregar()",
    "DROP TABLE postulacion",
    "DROP TABLE vacante",
    "DROP TABLE turno",
    "ALTER TABLE version_horario DROP CONSTRAINT ux_version_horario_id_horario",
    "DROP TYPE tipo_evento_turno",
    "DROP TYPE estado_vacante",
]


def upgrade() -> None:
    for sentencia in _UPGRADE:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _DOWNGRADE:
        op.execute(sentencia)

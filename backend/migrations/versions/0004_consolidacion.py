"""Marca de consolidación perezosa e índice de turnos sin consolidar (D20, D07)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-08
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_UPGRADE = [
    # D20: los turnos calculados con fecha anterior a consolidado_hasta ya se materializaron y consolidaron.
    # Una sola fila; NULL = todavía no se consolidó nada (se parte de la primera vigencia).
    # D27: desfase_demo es el adelanto del reloj de demo; vive en la misma fila para que el seed lo reinicie.
    """
    CREATE TABLE consolidacion_estado (
        id smallint PRIMARY KEY DEFAULT 1,
        consolidado_hasta date,
        desfase_demo interval NOT NULL DEFAULT '0',
        CONSTRAINT ck_consolidacion_estado_unica CHECK (id = 1)
    )
    """,
    "ALTER TABLE consolidacion_estado ENABLE ROW LEVEL SECURITY",
    "CREATE INDEX ix_turno_sin_consolidar ON turno (fin) WHERE consolidado_en IS NULL",
]

_DOWNGRADE = [
    "DROP INDEX ix_turno_sin_consolidar",
    "DROP TABLE consolidacion_estado",
]


def upgrade() -> None:
    for sentencia in _UPGRADE:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _DOWNGRADE:
        op.execute(sentencia)

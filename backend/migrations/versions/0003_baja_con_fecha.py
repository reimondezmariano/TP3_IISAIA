"""Estado BAJA y fecha de baja siempre juntos (D24)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-07
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_UPGRADE = [
    # D24: toda baja tiene fecha (último día activo) y solo una cuenta dada de baja la tiene.
    "ALTER TABLE usuario ADD CONSTRAINT ck_usuario_fecha_baja CHECK ((estado = 'BAJA') = (fecha_baja IS NOT NULL))",
]

_DOWNGRADE = [
    "ALTER TABLE usuario DROP CONSTRAINT ck_usuario_fecha_baja",
]


def upgrade() -> None:
    for sentencia in _UPGRADE:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _DOWNGRADE:
        op.execute(sentencia)

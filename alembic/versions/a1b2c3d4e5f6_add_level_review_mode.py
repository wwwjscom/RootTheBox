"""add_level_review_mode

Revision ID: a1b2c3d4e5f6
Revises: d3b1c5f8a901
Create Date: 2026-03-30 00:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

from alembic import op

try:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
except Exception:
    conn = None
    inspector = None


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "d3b1c5f8a901"
branch_labels = None
depends_on = None


def _table_has_column(table, column):
    if not inspector:
        return True
    for col in inspector.get_columns(table):
        if column in col["name"]:
            return True
    return False


def upgrade():
    if not _table_has_column("game_level", "_review_mode"):
        op.add_column(
            "game_level",
            sa.Column("_review_mode", sa.Boolean(), nullable=False, server_default="0"),
        )


def downgrade():
    if _table_has_column("game_level", "_review_mode"):
        op.drop_column("game_level", "_review_mode")

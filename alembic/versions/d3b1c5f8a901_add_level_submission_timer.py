"""add_level_submission_timer

Revision ID: d3b1c5f8a901
Revises: 1ee5b63e716f
Create Date: 2026-02-22 16:10:00.000000

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
revision = "d3b1c5f8a901"
down_revision = "1ee5b63e716f"
branch_labels = None
depends_on = None


def _table_has_column(table, column):
    if not inspector:
        return True
    for col in inspector.get_columns(table):
        if column in col["name"]:
            return True
    return False


def _table_exists(table):
    if not inspector:
        return True
    return table in inspector.get_table_names()


def upgrade():
    # Store per-level timer configuration directly on the game_level row.
    if not _table_has_column("game_level", "_flag_submission_timer_minutes"):
        op.add_column(
            "game_level",
            sa.Column(
                "_flag_submission_timer_minutes",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )
    # Track per-user timer state so each player gets an independent countdown.
    if not _table_exists("user_level_timer"):
        op.create_table(
            "user_level_timer",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created", sa.DateTime(), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("game_level_id", sa.Integer(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["game_level_id"], ["game_level.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id", "game_level_id", name="uq_user_level_timer_user_game_level"
            ),
        )


def downgrade():
    # Remove per-user timer state first because it depends on game levels and users.
    if _table_exists("user_level_timer"):
        op.drop_table("user_level_timer")
    # Then remove timer configuration from levels.
    if _table_has_column("game_level", "_flag_submission_timer_minutes"):
        op.drop_column("game_level", "_flag_submission_timer_minutes")

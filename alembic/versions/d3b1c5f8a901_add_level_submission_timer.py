"""add_level_submission_timer

Revision ID: d3b1c5f8a901
Revises: 1ee5b63e716f
Create Date: 2026-02-22 16:10:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "d3b1c5f8a901"
down_revision = "1ee5b63e716f"
branch_labels = None
depends_on = None


def upgrade():
    # Store per-level timer configuration directly on the game_level row.
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
    op.drop_table("user_level_timer")
    # Then remove timer configuration from levels.
    op.drop_column("game_level", "_flag_submission_timer_minutes")

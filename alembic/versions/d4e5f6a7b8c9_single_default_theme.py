"""single_default_theme

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-09 18:00:00.000000

Phase 2.1c ships one theme, "Default" (vendor Bootstrap 5 + rtb.css). Collapse
every legacy theme into it: create Default if missing, move all users onto it,
then delete the other themes and their files.
"""

from uuid import uuid4

import sqlalchemy as sa

from alembic import op

try:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
except Exception:
    conn = None
    inspector = None

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None

DEFAULT_THEME = "Default"
DEFAULT_FILES = ("bootstrap.min.css", "rtb.css")


def _has_table(table_name):
    if not inspector:
        return True
    return table_name in inspector.get_table_names()


def _default_theme_id(bind):
    """Id of the Default theme, creating it (and its files) if needed"""
    select_id = sa.text("SELECT id FROM theme WHERE _name = :name")
    theme_id = bind.execute(select_id, {"name": DEFAULT_THEME}).scalar()
    if theme_id is None:
        bind.execute(
            sa.text(
                "INSERT INTO theme (created, uuid, _name) "
                "VALUES (CURRENT_TIMESTAMP, :uuid, :name)"
            ),
            {"uuid": str(uuid4()), "name": DEFAULT_THEME},
        )
        theme_id = bind.execute(select_id, {"name": DEFAULT_THEME}).scalar()
    bind.execute(
        sa.text("DELETE FROM theme_file WHERE theme_id = :theme_id"),
        {"theme_id": theme_id},
    )
    for file_name in DEFAULT_FILES:
        bind.execute(
            sa.text(
                "INSERT INTO theme_file (created, theme_id, _file_name) "
                "VALUES (CURRENT_TIMESTAMP, :theme_id, :file_name)"
            ),
            {"theme_id": theme_id, "file_name": file_name},
        )
    return theme_id


def upgrade():
    if not _has_table("theme") or not _has_table("theme_file"):
        return
    bind = op.get_bind()
    default_id = _default_theme_id(bind)
    if _has_table("user"):
        bind.execute(
            sa.text("UPDATE user SET theme_id = :default_id"),
            {"default_id": default_id},
        )
    bind.execute(
        sa.text("DELETE FROM theme_file WHERE theme_id != :default_id"),
        {"default_id": default_id},
    )
    bind.execute(
        sa.text("DELETE FROM theme WHERE id != :default_id"),
        {"default_id": default_id},
    )


def downgrade():
    # Which theme each user had is not recorded anywhere -- irreversible,
    # same convention as b2c3d4e5f6a7 / ffe623ae412.
    print("No downgrade for this")

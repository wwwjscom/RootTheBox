"""bootstrap_out_of_theme

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-14 15:00:00.000000

Phase 2.2: Bootstrap is the base every theme sits on, so main.html loads it from
static/vendor/bootstrap/ on every page. Drop it from the theme file lists
(theme files are served from static/css/themes/, where it no longer lives).
"""

import sqlalchemy as sa

from alembic import op

try:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
except Exception:
    conn = None
    inspector = None

# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None

BOOTSTRAP_FILE = "bootstrap.min.css"
DEFAULT_THEME = "Default"


def _has_table(table_name):
    if not inspector:
        return True
    return table_name in inspector.get_table_names()


def upgrade():
    if not _has_table("theme_file"):
        return
    op.get_bind().execute(
        sa.text("DELETE FROM theme_file WHERE _file_name = :file_name"),
        {"file_name": BOOTSTRAP_FILE},
    )


def downgrade():
    if not _has_table("theme") or not _has_table("theme_file"):
        return
    bind = op.get_bind()
    theme_id = bind.execute(
        sa.text("SELECT id FROM theme WHERE _name = :name"), {"name": DEFAULT_THEME}
    ).scalar()
    if theme_id is None:
        return
    bind.execute(
        sa.text(
            "INSERT INTO theme_file (created, theme_id, _file_name) "
            "VALUES (CURRENT_TIMESTAMP, :theme_id, :file_name)"
        ),
        {"theme_id": theme_id, "file_name": BOOTSTRAP_FILE},
    )

"""curate_bootstrap5_themes

Phase 2.1b (theme curation): the BS2 Bootswatch theme set is being reduced
to the 8 themes with an official Bootswatch 5.3.3 release (+ default
Bootstrap, + the 2 custom themes 386/cyberpunk). Amelia, Readable, Spruce,
and Geocities have no Bootswatch 5 equivalent and are dropped.

For any existing installation:
  1. Any user whose theme_id points at one of the 4 dropped themes is
     reassigned to the default theme (Cyborg) so no user is left pointing
     at a deleted row.
  2. The 4 dropped themes' Theme + ThemeFile rows are deleted (in that
     order re: the user reassignment, so the FK is never dangling).
  3. The "386" custom theme's file list is updated in place: its old
     386.css/386.responsive.css ThemeFile rows (superseded by a single
     386.min.css, ported to layer on the Bootstrap 5 base) are removed
     and a 386.min.css row is added if not already present. 386.js is
     untouched (unchanged file, still referenced).

Idempotent: re-running finds no matching dropped-theme rows / already-
correct 386 file list and does nothing on the second pass.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-22 00:00:00.000000

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
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

DROPPED_THEMES = ("Amelia", "Readable", "Spruce", "Geocities")
DEFAULT_THEME = "Cyborg"
OLD_386_FILES = ("386.css", "386.responsive.css")
NEW_386_FILE = "386.min.css"


def _has_table(table_name):
    if not inspector:
        return True
    return table_name in inspector.get_table_names()


def upgrade():
    if not _has_table("theme") or not _has_table("theme_file"):
        return
    bind = op.get_bind()

    default_id = bind.execute(
        sa.text("SELECT id FROM theme WHERE _name = :name"),
        {"name": DEFAULT_THEME},
    ).scalar()

    for dropped_name in DROPPED_THEMES:
        dropped_id = bind.execute(
            sa.text("SELECT id FROM theme WHERE _name = :name"),
            {"name": dropped_name},
        ).scalar()
        if dropped_id is None:
            continue  # already removed by a prior run of this migration
        if default_id is not None and _has_table("user"):
            bind.execute(
                sa.text(
                    "UPDATE user SET theme_id = :default_id WHERE theme_id = :dropped_id"
                ),
                {"default_id": default_id, "dropped_id": dropped_id},
            )
        bind.execute(
            sa.text("DELETE FROM theme_file WHERE theme_id = :dropped_id"),
            {"dropped_id": dropped_id},
        )
        bind.execute(
            sa.text("DELETE FROM theme WHERE id = :dropped_id"),
            {"dropped_id": dropped_id},
        )

    theme_386_id = bind.execute(
        sa.text("SELECT id FROM theme WHERE _name = '386'")
    ).scalar()
    if theme_386_id is not None:
        bind.execute(
            sa.text(
                "DELETE FROM theme_file WHERE theme_id = :theme_id AND _file_name IN :old_files"
            ).bindparams(sa.bindparam("old_files", expanding=True)),
            {"theme_id": theme_386_id, "old_files": list(OLD_386_FILES)},
        )
        has_new_file = bind.execute(
            sa.text(
                "SELECT 1 FROM theme_file WHERE theme_id = :theme_id AND _file_name = :new_file"
            ),
            {"theme_id": theme_386_id, "new_file": NEW_386_FILE},
        ).scalar()
        if not has_new_file:
            bind.execute(
                sa.text(
                    "INSERT INTO theme_file (created, theme_id, _file_name) "
                    "VALUES (CURRENT_TIMESTAMP, :theme_id, :new_file)"
                ),
                {"theme_id": theme_386_id, "new_file": NEW_386_FILE},
            )


def downgrade():
    # Deleting a theme drops which users were on it (they're reassigned to
    # Cyborg first, and that per-user history isn't tracked anywhere) --
    # same irreversible-data-migration shape as ffe623ae412. Not restorable.
    print("No downgrade for this")

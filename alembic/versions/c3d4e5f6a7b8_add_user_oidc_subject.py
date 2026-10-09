"""add_user_oidc_subject

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-09 12:00:00.000000

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
revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
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
    # Link users to their OIDC identity provider subject ('sub' claim).
    # SQLite can't ADD a UNIQUE column, so uniqueness comes from the index.
    if not _table_has_column("user", "oidc_subject"):
        op.add_column(
            "user", sa.Column("oidc_subject", sa.String(length=255), nullable=True)
        )
        op.create_index("ix_user_oidc_subject", "user", ["oidc_subject"], unique=True)


def downgrade():
    if _table_has_column("user", "oidc_subject"):
        op.drop_index("ix_user_oidc_subject", table_name="user")
        op.drop_column("user", "oidc_subject")

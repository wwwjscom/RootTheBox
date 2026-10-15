"""require_flag_order

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-15 12:00:00.000000

Flags used to get their order lazily when it was read, which could leave
flag._order empty (XML imports never set it) or duplicated (new flags were
numbered without counting locked flags). A locked flag with no order 500'd
/admin/view/game_objects.

Renumber every box's flags 1..n, keeping the order admins and players see
(numbered flags first, ties by id, empty orders last), then make the column
NOT NULL. Boxes already numbered 1..n are left untouched, so this is safe to
run again.
"""

from collections import defaultdict

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None

flag = sa.table(
    "flag",
    sa.column("id", sa.Integer),
    sa.column("box_id", sa.Integer),
    sa.column("_order", sa.Integer),
)


def _order_nullable():
    for col in sa.inspect(op.get_bind()).get_columns("flag"):
        if col["name"] == "_order":
            return col["nullable"]
    return False


def _renumber_flags():
    conn = op.get_bind()
    boxes = defaultdict(list)
    for flag_id, box_id, order in conn.execute(
        sa.select(flag.c.id, flag.c.box_id, flag.c._order)
    ):
        boxes[box_id].append((order is None, order or 0, flag_id, order))
    for rows in boxes.values():
        for new_order, (_, _, flag_id, order) in enumerate(sorted(rows), start=1):
            if order != new_order:
                conn.execute(
                    flag.update().where(flag.c.id == flag_id).values(_order=new_order)
                )


def upgrade():
    _renumber_flags()
    if _order_nullable():
        with op.batch_alter_table("flag") as batch_op:
            batch_op.alter_column("_order", existing_type=sa.Integer(), nullable=False)


def downgrade():
    # The original empty orders are not restored; nothing depends on them.
    if not _order_nullable():
        with op.batch_alter_table("flag") as batch_op:
            batch_op.alter_column("_order", existing_type=sa.Integer(), nullable=True)

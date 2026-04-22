"""flow folder user_id ON DELETE SET NULL

Revision ID: 6fd608236310
Revises: d882b36fff8d
Create Date: 2026-04-22 11:29:13.089395

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6fd608236310"
down_revision: Union[str, None] = "d882b36fff8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The project's naming convention (see alembic/env.py) produces
# fk_<table>_<column>_<referred_table>. For `user_id` referencing `user.id`
# that yields fk_flow_user_id_user and fk_folder_user_id_user — which match
# the constraint names that actually exist in SQLite's sqlite_master today.
FLOW_FK = "fk_flow_user_id_user"
FOLDER_FK = "fk_folder_user_id_user"


def _alter_user_fk(table: str, fk_name: str, ondelete: str | None) -> None:
    """Rewrite the user_id FK on `table` with the given ondelete behavior.

    Uses batch_alter_table(recreate="always") so SQLite's copy-and-rename
    rewrite happens cleanly regardless of whether the original FK was
    named or inline.
    """
    with op.batch_alter_table(table, recreate="always") as batch_op:
        # Drop the existing FK by name when present; on dialects where the
        # FK was unnamed/inline, recreate still handles it during the
        # copy-and-rename dance.
        try:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
        except Exception:
            pass
        batch_op.create_foreign_key(
            fk_name,
            "user",
            ["user_id"],
            ["id"],
            ondelete=ondelete,
        )


def upgrade() -> None:
    # Columns are already nullable in the model; this is a defensive no-op
    # for any environment that somehow ended up with a NOT NULL column.
    with op.batch_alter_table("flow") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Uuid(), nullable=True)
    with op.batch_alter_table("folder") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Uuid(), nullable=True)

    _alter_user_fk("flow", FLOW_FK, ondelete="SET NULL")
    _alter_user_fk("folder", FOLDER_FK, ondelete="SET NULL")


def downgrade() -> None:
    # Revert to the prior behavior: a plain FK with no explicit ondelete
    # (default NO ACTION).
    _alter_user_fk("folder", FOLDER_FK, ondelete=None)
    _alter_user_fk("flow", FLOW_FK, ondelete=None)

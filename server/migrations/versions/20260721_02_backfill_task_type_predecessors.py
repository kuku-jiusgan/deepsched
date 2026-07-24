"""Backfill missing predecessor lists on standard task types.

Revision ID: 20260721_02
Revises: 20260721_01
"""
from alembic import op
import sqlalchemy as sa


revision = "20260721_02"
down_revision = "20260721_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    task_type_config = sa.table(
        "task_type_config",
        sa.column("predecessor_type_ids", sa.JSON()),
    )
    op.execute(
        task_type_config.update()
        .where(task_type_config.c.predecessor_type_ids.is_(None))
        .values(predecessor_type_ids=[])
    )


def downgrade() -> None:
    pass

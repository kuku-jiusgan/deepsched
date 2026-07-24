"""Add configurable page permissions for system roles.

Revision ID: 20260721_03
Revises: 20260721_02
"""
from alembic import op
import sqlalchemy as sa


revision = "20260721_03"
down_revision = "20260721_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "role_permission",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("page_key", sa.String(length=100), nullable=False),
        sa.Column("can_view", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_operate", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("role", "page_key"),
    )


def downgrade() -> None:
    op.drop_table("role_permission")

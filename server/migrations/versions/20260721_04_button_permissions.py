"""Add per-button permissions to role page settings.

Revision ID: 20260721_04
Revises: 20260721_03
"""
from alembic import op
import sqlalchemy as sa


revision = "20260721_04"
down_revision = "20260721_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("role_permission", sa.Column("action_permissions", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("role_permission", "action_permissions")

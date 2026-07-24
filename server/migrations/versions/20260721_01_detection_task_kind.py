"""Add the project discriminator used by standalone detection tasks.

Revision ID: 20260721_01
Revises: 20260718_01
"""
from alembic import op
import sqlalchemy as sa


revision = "20260721_01"
down_revision = "20260718_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project",
        sa.Column("project_kind", sa.String(length=20), nullable=False, server_default="project"),
    )


def downgrade() -> None:
    op.drop_column("project", "project_kind")

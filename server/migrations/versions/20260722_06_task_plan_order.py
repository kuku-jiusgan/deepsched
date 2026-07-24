"""增加项目计划任务排序

Revision ID: 20260722_06
Revises: 20260722_05
"""
from alembic import op
import sqlalchemy as sa

revision = "20260722_06"
down_revision = "20260722_05"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("task", sa.Column("plan_order", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("task", "plan_order")

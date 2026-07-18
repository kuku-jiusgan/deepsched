"""Establish the managed schema baseline and multi-instance infrastructure tables.

Revision ID: 20260718_01
Revises: None
"""
from alembic import op

from app.core.database import Base
from app.models import models  # noqa: F401


revision = "20260718_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The legacy application predates Alembic. create_all is intentionally used
    # once in this baseline so existing installations gain only missing tables,
    # while clean installations receive the complete current schema.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    # Existing business tables may contain production data and must never be
    # dropped by downgrading the adoption baseline.
    pass

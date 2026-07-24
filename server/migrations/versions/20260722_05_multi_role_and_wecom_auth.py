"""补齐多角色及企业微信登录状态

Revision ID: 20260722_05
Revises: 20260721_04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260722_05"
down_revision = "20260721_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user", sa.Column("roles", sa.JSON(), nullable=True))
    op.create_table(
        "wecom_oauth_state",
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("state_hash"),
    )
    op.create_index(
        op.f("ix_wecom_oauth_state_expires_at"),
        "wecom_oauth_state",
        ["expires_at"],
        unique=False,
    )

    connection = op.get_bind()
    users = sa.table(
        "user",
        sa.column("id", sa.Integer()),
        sa.column("role", sa.String()),
        sa.column("roles", sa.JSON()),
    )
    for user_id, role in connection.execute(sa.select(users.c.id, users.c.role)):
        normalized_role = "技术员" if role == "分析员" else role
        connection.execute(
            users.update().where(users.c.id == user_id).values(
                role=normalized_role,
                roles=[normalized_role],
            )
        )

    legacy_count = connection.execute(sa.text(
        "SELECT COUNT(*) FROM role_permission WHERE role = '分析员'"
    )).scalar()
    if legacy_count:
        connection.execute(sa.text("DELETE FROM role_permission WHERE role = '技术员'"))
        connection.execute(sa.text(
            "UPDATE role_permission SET role = '技术员' WHERE role = '分析员'"
        ))
    connection.execute(sa.text(
        "UPDATE alert_rule SET notify_roles = "
        "REPLACE(notify_roles, '\"分析员\"', '\"技术员\"') "
        "WHERE notify_roles IS NOT NULL"
    ))
    connection.execute(sa.text(
        "UPDATE push_channel_config SET "
        "wecom_corp_id = TRIM(wecom_corp_id), "
        "wecom_agent_id = TRIM(wecom_agent_id), "
        "wecom_secret = TRIM(wecom_secret)"
    ))


def downgrade() -> None:
    op.drop_index(op.f("ix_wecom_oauth_state_expires_at"), table_name="wecom_oauth_state")
    op.drop_table("wecom_oauth_state")
    op.drop_column("user", "roles")

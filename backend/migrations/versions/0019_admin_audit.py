"""admin action audit log

Revision ID: 0019_admin_audit
Revises: 0018_push_subscriptions
Create Date: 2026-08-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0019_admin_audit"
down_revision: str | None = "0018_push_subscriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_email", sa.String(320), nullable=False),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("target_user_id", sa.String(64), nullable=True),
        sa.Column("detail", JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_admin_audit_log_admin_email", "admin_audit_log", ["admin_email"])
    op.create_index("ix_admin_audit_log_action", "admin_audit_log", ["action"])
    op.create_index("ix_admin_audit_log_target_user_id", "admin_audit_log", ["target_user_id"])


def downgrade() -> None:
    op.drop_table("admin_audit_log")

"""subscriptions: recurring plan per user

Revision ID: 0011_subscriptions
Revises: 0010_chat_messages
Create Date: 2026-07-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_subscriptions"
down_revision: str | None = "0010_chat_messages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("tier", sa.String(16), nullable=False, server_default="free"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active", index=True),
        sa.Column("cadence", sa.String(16), nullable=False, server_default="monthly"),
        sa.Column("provider", sa.String(16), nullable=False, server_default="paystack"),
        sa.Column("provider_ref", sa.String(128), nullable=True, index=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("subscriptions")

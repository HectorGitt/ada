"""per-user notification preferences + unsubscribe token

Revision ID: 0016_notification_prefs
Revises: 0015_verification
Create Date: 2026-07-31
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_notification_prefs"
down_revision: str | None = "0015_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_prefs",
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("whatsapp_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("digest_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("unsubscribe_token", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_notification_prefs_unsubscribe_token", "notification_prefs", ["unsubscribe_token"]
    )


def downgrade() -> None:
    op.drop_table("notification_prefs")

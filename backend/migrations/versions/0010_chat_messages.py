"""chat_messages: persist the Ask Ada conversation per user

Revision ID: 0010_chat_messages
Revises: 0009_user_memories
Create Date: 2026-07-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_chat_messages"
down_revision: str | None = "0009_user_memories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=False, index=True
        ),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("chat_messages")

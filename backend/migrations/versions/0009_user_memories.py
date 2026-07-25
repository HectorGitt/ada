"""user_memories: durable per-user facts Ada learns from chat, embedded for recall

Revision ID: 0009_user_memories
Revises: 0008_merge_heads
Create Date: 2026-07-25
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0009_user_memories"
down_revision: str | None = "0008_merge_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_memories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=False, index=True
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="chat"),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("user_memories")

"""in-app intro conversation thread

Revision ID: 0021_intro_messages
Revises: 0020_employer_console
Create Date: 2026-08-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_intro_messages"
down_revision: str | None = "0020_employer_console"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "intro_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("intro_id", sa.String(64), sa.ForeignKey("intros.id"), nullable=False),
        sa.Column("sender", sa.String(16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_intro_messages_intro_id", "intro_messages", ["intro_id"])


def downgrade() -> None:
    op.drop_table("intro_messages")

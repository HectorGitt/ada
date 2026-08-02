"""guest-run access token hash

Revision ID: 0022_run_access_token
Revises: 0021_intro_messages
Create Date: 2026-08-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_run_access_token"
down_revision: str | None = "0021_intro_messages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("access_token_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "access_token_hash")

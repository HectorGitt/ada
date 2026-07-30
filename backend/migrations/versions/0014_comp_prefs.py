"""candidate compensation + work preference on profiles

Revision ID: 0014_comp_prefs
Revises: 0013_notifications
Create Date: 2026-07-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_comp_prefs"
down_revision: str | None = "0013_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("compensation", sa.String(120), nullable=True))
    op.add_column("profiles", sa.Column("work_pref", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "work_pref")
    op.drop_column("profiles", "compensation")

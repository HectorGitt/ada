"""verification credential: proctored assessments + identity attestation

Revision ID: 0015_verification
Revises: 0014_comp_prefs
Create Date: 2026-07-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_verification"
down_revision: str | None = "0014_comp_prefs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("identity_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("profiles", sa.Column("identity_method", sa.String(40), nullable=True))

    op.create_table(
        "assessments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("skill", sa.String(160), nullable=False),
        sa.Column("questions", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("answers", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("verdict", sa.String(16), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("integrity", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("evidence", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_assessments_user_id", "assessments", ["user_id"])
    op.create_index("ix_assessments_status", "assessments", ["status"])


def downgrade() -> None:
    op.drop_table("assessments")
    op.drop_column("profiles", "identity_method")
    op.drop_column("profiles", "identity_verified")

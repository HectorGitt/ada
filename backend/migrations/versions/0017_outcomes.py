"""candidate hiring-funnel outcomes (applied → interviewing → offer → hired)

Revision ID: 0017_outcomes
Revises: 0016_notification_prefs
Create Date: 2026-07-31
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_outcomes"
down_revision: str | None = "0016_notification_prefs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outcomes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("company", sa.String(256), nullable=False),
        sa.Column("role_title", sa.String(256), nullable=False),
        sa.Column("stage", sa.String(16), nullable=False, server_default="applied"),
        sa.Column("source", sa.String(16), nullable=False, server_default="one_click"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "job_id", name="uq_outcome_user_job"),
    )
    op.create_index("ix_outcomes_user_id", "outcomes", ["user_id"])
    op.create_index("ix_outcomes_job_id", "outcomes", ["job_id"])
    op.create_index("ix_outcomes_stage", "outcomes", ["stage"])


def downgrade() -> None:
    op.drop_table("outcomes")

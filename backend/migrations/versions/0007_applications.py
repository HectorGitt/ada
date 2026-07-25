"""applications table + applicant identity on profiles

Revision ID: 0007_applications
Revises: 0006_jobs_ingest
Create Date: 2026-07-25
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_applications"
down_revision: str | None = "0006_jobs_ingest"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("full_name", sa.String(160), nullable=True))
    op.add_column("profiles", sa.Column("phone", sa.String(40), nullable=True))
    op.create_table(
        "applications",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False, index=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("runs.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "job_id", name="uq_application_user_job"),
    )


def downgrade() -> None:
    op.drop_table("applications")
    op.drop_column("profiles", "phone")
    op.drop_column("profiles", "full_name")

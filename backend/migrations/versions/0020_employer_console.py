"""employer console: company profiles + saved candidates (shortlist)

Revision ID: 0020_employer_console
Revises: 0019_admin_audit
Create Date: 2026-08-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_employer_console"
down_revision: str | None = "0019_admin_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_profiles",
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("website", sa.String(512), nullable=True),
        sa.Column("industry", sa.String(120), nullable=True),
        sa.Column("size", sa.String(40), nullable=True),
        sa.Column("location", sa.String(160), nullable=True),
        sa.Column("about", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.String(1024), nullable=True),
        sa.Column("contact_name", sa.String(160), nullable=True),
        sa.Column("contact_title", sa.String(160), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "saved_candidates",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("employer_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("candidate_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("stage", sa.String(16), nullable=False, server_default="shortlisted"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("employer_id", "candidate_id", name="uq_saved_candidate"),
    )
    op.create_index("ix_saved_candidates_employer_id", "saved_candidates", ["employer_id"])
    op.create_index("ix_saved_candidates_candidate_id", "saved_candidates", ["candidate_id"])
    op.create_index("ix_saved_candidates_stage", "saved_candidates", ["stage"])


def downgrade() -> None:
    op.drop_table("saved_candidates")
    op.drop_table("company_profiles")

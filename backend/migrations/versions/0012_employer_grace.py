"""employer/candidate marketplace: account types, discoverable profiles, intros

Revision ID: 0012_employer_grace
Revises: 0011_subscriptions
Create Date: 2026-07-28
"""
from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

revision: str = "0012_employer_grace"
down_revision: str | None = "0011_subscriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBED_DIM = 768


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("account_type", sa.String(16), nullable=False, server_default="candidate"),
    )
    op.add_column("users", sa.Column("company", sa.String(200), nullable=True))

    op.add_column(
        "profiles",
        sa.Column("discoverable", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("profiles", sa.Column("headline", sa.String(200), nullable=True))
    op.add_column("profiles", sa.Column("location", sa.String(160), nullable=True))
    op.add_column(
        "profiles", sa.Column("embedding", pgvector.sqlalchemy.Vector(EMBED_DIM), nullable=True)
    )
    op.add_column("profiles", sa.Column("insights", sa.dialects.postgresql.JSONB(), nullable=True))
    op.create_index("ix_profiles_discoverable", "profiles", ["discoverable"])

    op.add_column("jobs", sa.Column("posted_by", sa.String(64), nullable=True))
    op.create_foreign_key(
        "fk_jobs_posted_by", "jobs", "users", ["posted_by"], ["id"]
    )
    op.create_index("ix_jobs_posted_by", "jobs", ["posted_by"])

    op.create_table(
        "intros",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("employer_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("candidate_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="requested"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("employer_id", "candidate_id", "job_id", name="uq_intro"),
    )
    op.create_index("ix_intros_employer_id", "intros", ["employer_id"])
    op.create_index("ix_intros_candidate_id", "intros", ["candidate_id"])
    op.create_index("ix_intros_job_id", "intros", ["job_id"])
    op.create_index("ix_intros_status", "intros", ["status"])


def downgrade() -> None:
    op.drop_table("intros")
    op.drop_index("ix_jobs_posted_by", table_name="jobs")
    op.drop_constraint("fk_jobs_posted_by", "jobs", type_="foreignkey")
    op.drop_column("jobs", "posted_by")
    op.drop_index("ix_profiles_discoverable", table_name="profiles")
    op.drop_column("profiles", "insights")
    op.drop_column("profiles", "embedding")
    op.drop_column("profiles", "location")
    op.drop_column("profiles", "headline")
    op.drop_column("profiles", "discoverable")
    op.drop_column("users", "company")
    op.drop_column("users", "account_type")

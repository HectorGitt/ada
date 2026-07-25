"""jobs: ingestion columns + (source, external_id) dedup key; embedding nullable

Revision ID: 0006_jobs_ingest
Revises: 0005_password
Create Date: 2026-07-25
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_jobs_ingest"
down_revision: str | None = "0005_password"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("source", sa.String(32), nullable=False, server_default="seed"))
    op.add_column("jobs", sa.Column("external_id", sa.String(256), nullable=True))
    op.add_column(
        "jobs", sa.Column("remote", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("jobs", sa.Column("url", sa.String(1024), nullable=True))
    op.add_column("jobs", sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True))
    # Pre-ingestion rows came from the dev seed corpus: key them by their own id.
    op.execute("UPDATE jobs SET external_id = 'seed-' || id::text WHERE external_id IS NULL")
    op.alter_column("jobs", "external_id", nullable=False)
    op.create_unique_constraint("uq_jobs_source_external", "jobs", ["source", "external_id"])
    # Listings land even without model creds; embedding is backfilled when creds exist.
    op.alter_column("jobs", "embedding", nullable=True)


def downgrade() -> None:
    op.alter_column("jobs", "embedding", nullable=False)
    op.drop_constraint("uq_jobs_source_external", "jobs", type_="unique")
    op.drop_column("jobs", "posted_at")
    op.drop_column("jobs", "url")
    op.drop_column("jobs", "remote")
    op.drop_column("jobs", "external_id")
    op.drop_column("jobs", "source")

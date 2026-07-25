"""uploaded_documents: user CV uploads (extracted text + GCS archive pointer)

Revision ID: 0007_uploaded_documents
Revises: 0006_jobs_ingest
Create Date: 2026-07-25
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_uploaded_documents"
down_revision: str | None = "0006_jobs_ingest"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "uploaded_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=False, index=True
        ),
        sa.Column("filename", sa.String(length=256), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("gcs_uri", sa.String(length=1024), nullable=True),
        sa.Column("cv_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("uploaded_documents")

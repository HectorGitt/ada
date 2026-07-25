"""merge heads: applications + uploaded_documents (parallel branches off 0006)

Revision ID: 0008_merge_heads
Revises: 0007_applications, 0007_uploaded_documents
Create Date: 2026-07-25
"""
from collections.abc import Sequence

revision: str = "0008_merge_heads"
down_revision: str | Sequence[str] | None = ("0007_applications", "0007_uploaded_documents")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

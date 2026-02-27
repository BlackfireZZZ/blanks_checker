"""ingested_batches: S3 key and checksum instead of records

Revision ID: a1b2c3d4e5f6
Revises: 814efd068190
Create Date: 2026-02-19

Raw batch payloads are stored in MinIO; PostgreSQL holds only metadata.
If ingested_batches already contains rows, truncate or use Option B (one-time
backfill) before running this migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "814efd068190"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ingested_batches",
        sa.Column("s3_key", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "ingested_batches",
        sa.Column("checksum", sa.String(length=64), nullable=True),
    )
    op.drop_column("ingested_batches", "records")
    # Existing rows have NULL s3_key/checksum; truncate so we can set NOT NULL (Option A: wipe and re-ingest).
    op.execute("TRUNCATE TABLE ingested_batches")
    op.alter_column(
        "ingested_batches",
        "s3_key",
        existing_type=sa.String(512),
        nullable=False,
    )
    op.alter_column(
        "ingested_batches",
        "checksum",
        existing_type=sa.String(64),
        nullable=False,
    )


def downgrade() -> None:
    op.add_column(
        "ingested_batches",
        sa.Column("records", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.alter_column(
        "ingested_batches",
        "records",
        server_default=None,
    )
    op.drop_column("ingested_batches", "checksum")
    op.drop_column("ingested_batches", "s3_key")

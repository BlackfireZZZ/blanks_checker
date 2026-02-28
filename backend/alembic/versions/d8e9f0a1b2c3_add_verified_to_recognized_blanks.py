"""add verified to recognized_blanks

Revision ID: d8e9f0a1b2c3
Revises: b7c8d9e0f1a2
Create Date: 2026-02-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recognized_blanks",
        sa.Column("verified", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "recognized_blanks",
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "recognized_blanks",
        sa.Column("verified_by", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("recognized_blanks", "verified_by")
    op.drop_column("recognized_blanks", "verified_at")
    op.drop_column("recognized_blanks", "verified")

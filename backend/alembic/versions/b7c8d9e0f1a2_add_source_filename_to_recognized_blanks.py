"""add source_filename to recognized_blanks

Revision ID: b7c8d9e0f1a2
Revises: 9d1fa29abceb
Create Date: 2026-02-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "9d1fa29abceb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recognized_blanks",
        sa.Column("source_filename", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("recognized_blanks", "source_filename")

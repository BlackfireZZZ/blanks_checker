"""add_user_login

Revision ID: c5e6f7a8b9c0
Revises: b7c8d9e0f1a2
Create Date: 2026-02-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("login", sa.String(255), nullable=True))
    op.execute(
        "UPDATE users SET login = COALESCE(email, 'user_' || id::text) WHERE login IS NULL"
    )
    op.alter_column(
        "users",
        "login",
        existing_type=sa.String(255),
        nullable=False,
    )
    op.create_unique_constraint("uq_users_login", "users", ["login"])


def downgrade() -> None:
    op.drop_constraint("uq_users_login", "users", type_="unique")
    op.drop_column("users", "login")

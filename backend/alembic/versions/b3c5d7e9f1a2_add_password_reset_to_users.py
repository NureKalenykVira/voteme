"""add password reset to users

Revision ID: b3c5d7e9f1a2
Revises: 9b4e2f1a7c3d
Create Date: 2026-05-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3c5d7e9f1a2"
down_revision: Union[str, Sequence[str], None] = "9b4e2f1a7c3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_reset_token", sa.String(128), nullable=True),
    )
    op.create_unique_constraint(
        "uq_users_password_reset_token", "users", ["password_reset_token"]
    )
    op.add_column(
        "users",
        sa.Column(
            "password_reset_token_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_constraint("uq_users_password_reset_token", "users", type_="unique")
    op.drop_column("users", "password_reset_token_expires_at")
    op.drop_column("users", "password_reset_token")

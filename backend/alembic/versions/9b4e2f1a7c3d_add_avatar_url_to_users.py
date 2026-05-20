"""add avatar_url to users

Revision ID: 9b4e2f1a7c3d
Revises: 7e3f9a1b2c4d
Create Date: 2026-05-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9b4e2f1a7c3d"
down_revision: Union[str, Sequence[str], None] = "7e3f9a1b2c4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")

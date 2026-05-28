"""m5 add election tx hashes to votings

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-05-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, Sequence[str], None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "votings",
        sa.Column("publish_tx_hash", sa.String(length=66), nullable=True),
    )
    op.add_column(
        "votings",
        sa.Column("finalize_tx_hash", sa.String(length=66), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("votings", "finalize_tx_hash")
    op.drop_column("votings", "publish_tx_hash")

"""m6 add vote results

Revision ID: a1b2c3d4e5f6
Revises: f3a4b5c6d7e8
Create Date: 2026-05-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vote_results",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "voting_id",
            sa.UUID(),
            sa.ForeignKey("votings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "option_id",
            sa.UUID(),
            sa.ForeignKey("ballot_options.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "votes_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "voting_id", "option_id", name="uq_vote_result_voting_option"
        ),
    )
    op.create_index(
        "ix_vote_results_voting_id",
        "vote_results",
        ["voting_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_vote_results_voting_id", table_name="vote_results")
    op.drop_table("vote_results")

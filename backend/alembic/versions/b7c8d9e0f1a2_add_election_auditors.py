"""add election auditors

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-05-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "election_auditors",
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
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
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
            "voting_id", "user_id", name="uq_election_auditor_voting_user"
        ),
    )
    op.create_index(
        op.f("ix_election_auditors_voting_id"),
        "election_auditors",
        ["voting_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_election_auditors_user_id"),
        "election_auditors",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_election_auditors_user_id"), table_name="election_auditors"
    )
    op.drop_index(
        op.f("ix_election_auditors_voting_id"), table_name="election_auditors"
    )
    op.drop_table("election_auditors")

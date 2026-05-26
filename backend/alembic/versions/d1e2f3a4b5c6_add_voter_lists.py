"""add voter lists

Revision ID: d1e2f3a4b5c6
Revises: c4d6e8a0b2f3
Create Date: 2026-05-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c4d6e8a0b2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "voter_lists",
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
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "invited_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("voting_id", "email", name="uq_voter_list_email"),
    )
    op.create_index(
        op.f("ix_voter_lists_voting_id"),
        "voter_lists",
        ["voting_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voter_lists_email"),
        "voter_lists",
        ["email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voter_lists_user_id"),
        "voter_lists",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_voter_lists_user_id"), table_name="voter_lists")
    op.drop_index(op.f("ix_voter_lists_email"), table_name="voter_lists")
    op.drop_index(op.f("ix_voter_lists_voting_id"), table_name="voter_lists")
    op.drop_table("voter_lists")

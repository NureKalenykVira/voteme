"""m4 votes and blockchain records

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-05-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


blockchain_record_status_enum = postgresql.ENUM(
    "pending",
    "confirmed",
    "failed",
    name="blockchain_record_status",
    create_type=False,
)


def upgrade() -> None:
    blockchain_record_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "votes",
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
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "option_id",
            sa.UUID(),
            sa.ForeignKey("ballot_options.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("commitment_hash", sa.String(length=64), nullable=False),
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "voting_id", "user_id", name="uq_votes_user_voting"
        ),
    )
    op.create_index("ix_votes_voting_id", "votes", ["voting_id"], unique=False)
    op.create_index("ix_votes_user_id", "votes", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_votes_option_id"), "votes", ["option_id"], unique=False
    )
    op.create_index(
        op.f("ix_votes_commitment_hash"),
        "votes",
        ["commitment_hash"],
        unique=False,
    )

    op.create_table(
        "blockchain_records",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "vote_id",
            sa.UUID(),
            sa.ForeignKey("votes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tx_hash", sa.String(length=66), nullable=True),
        sa.Column(
            "status",
            blockchain_record_status_enum,
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "confirmed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vote_id"),
    )
    op.create_index(
        op.f("ix_blockchain_records_vote_id"),
        "blockchain_records",
        ["vote_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_blockchain_records_tx_hash"),
        "blockchain_records",
        ["tx_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_blockchain_records_tx_hash"), table_name="blockchain_records"
    )
    op.drop_index(
        op.f("ix_blockchain_records_vote_id"), table_name="blockchain_records"
    )
    op.drop_table("blockchain_records")

    op.drop_index(op.f("ix_votes_commitment_hash"), table_name="votes")
    op.drop_index(op.f("ix_votes_option_id"), table_name="votes")
    op.drop_index("ix_votes_user_id", table_name="votes")
    op.drop_index("ix_votes_voting_id", table_name="votes")
    op.drop_table("votes")

    blockchain_record_status_enum.drop(op.get_bind(), checkfirst=True)

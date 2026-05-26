"""m2 voting and ballot

Revision ID: c4d6e8a0b2f3
Revises: b3c5d7e9f1a2
Create Date: 2026-05-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c4d6e8a0b2f3"
down_revision: Union[str, Sequence[str], None] = "b3c5d7e9f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


voting_status_enum = postgresql.ENUM(
    "draft",
    "published",
    "active",
    "finished",
    "archived",
    name="voting_status",
    create_type=False,
)

voting_access_type_enum = postgresql.ENUM(
    "public",
    "private",
    name="voting_access_type",
    create_type=False,
)


def upgrade() -> None:
    voting_status_enum.create(op.get_bind(), checkfirst=True)
    voting_access_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "votings",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("access_type", voting_access_type_enum, nullable=False),
        sa.Column(
            "is_anonymous",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("invitation_code", sa.String(length=64), nullable=True),
        sa.Column(
            "start_date_time", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "end_date_time", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "status",
            voting_status_enum,
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "created_by",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invitation_code"),
        sa.CheckConstraint(
            "end_date_time > start_date_time",
            name="ck_votings_end_after_start",
        ),
    )

    op.create_index(
        "ix_votings_status_end_date_time",
        "votings",
        ["status", "end_date_time"],
        unique=False,
    )
    op.create_index(
        "ix_votings_created_by_status",
        "votings",
        ["created_by", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_votings_status"), "votings", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_votings_start_date_time"),
        "votings",
        ["start_date_time"],
        unique=False,
    )
    op.create_index(
        op.f("ix_votings_end_date_time"),
        "votings",
        ["end_date_time"],
        unique=False,
    )
    op.create_index(
        op.f("ix_votings_created_by"),
        "votings",
        ["created_by"],
        unique=False,
    )

    op.create_table(
        "ballot_options",
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
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("photo_url", sa.String(length=500), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "voting_id", "order_index", name="uq_ballot_option_order"
        ),
    )
    op.create_index(
        op.f("ix_ballot_options_voting_id"),
        "ballot_options",
        ["voting_id"],
        unique=False,
    )

    op.create_table(
        "voting_participations",
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
            "participated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "voting_id", "user_id", name="uq_voting_participation_user"
        ),
    )
    op.create_index(
        op.f("ix_voting_participations_voting_id"),
        "voting_participations",
        ["voting_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voting_participations_user_id"),
        "voting_participations",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_voting_participations_user_id"),
        table_name="voting_participations",
    )
    op.drop_index(
        op.f("ix_voting_participations_voting_id"),
        table_name="voting_participations",
    )
    op.drop_table("voting_participations")

    op.drop_index(
        op.f("ix_ballot_options_voting_id"), table_name="ballot_options"
    )
    op.drop_table("ballot_options")

    op.drop_index(op.f("ix_votings_created_by"), table_name="votings")
    op.drop_index(op.f("ix_votings_end_date_time"), table_name="votings")
    op.drop_index(op.f("ix_votings_start_date_time"), table_name="votings")
    op.drop_index(op.f("ix_votings_status"), table_name="votings")
    op.drop_index("ix_votings_created_by_status", table_name="votings")
    op.drop_index("ix_votings_status_end_date_time", table_name="votings")
    op.drop_table("votings")

    voting_access_type_enum.drop(op.get_bind(), checkfirst=True)
    voting_status_enum.drop(op.get_bind(), checkfirst=True)

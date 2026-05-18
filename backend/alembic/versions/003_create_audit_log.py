"""create_audit_log

Revision ID: 3a1f8c2d9e4b
Revises: ebb0ce687a72
Create Date: 2026-05-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "3a1f8c2d9e4b"
down_revision: Union[str, Sequence[str], None] = "ebb0ce687a72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column(
            "actor_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("entry_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        op.f("ix_audit_log_actor_id"),
        "audit_log",
        ["actor_id"],
        unique=False,
    )

    op.execute(
        "INSERT INTO audit_log (action, actor_id, data, previous_hash, entry_hash) "
        "VALUES ("
        "'GENESIS', "
        "NULL, "
        "NULL, "
        "'0000000000000000000000000000000000000000000000000000000000000000', "
        "'9ed9b8091629a72699f9de6e263ae2c7a018a1d904ff0e8e86bb053ba318efd5'"
        ")"
    )


def downgrade() -> None:
    op.drop_table("audit_log")

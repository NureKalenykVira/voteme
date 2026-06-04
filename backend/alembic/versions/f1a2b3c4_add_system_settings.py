"""add system_settings table

Revision ID: f1a2b3c4
Revises: e5f6a7b8c9d0
Create Date: 2026-06-02 00:00:00.000000

Introduces a key/value configuration store for platform-wide settings.
Seeded with four default entries on creation.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.bulk_insert(
        sa.table(
            "system_settings",
            sa.column("key", sa.String),
            sa.column("value", sa.String),
        ),
        [
            {"key": "max_free_votings_per_month", "value": "12"},
            {"key": "maintenance_mode", "value": "false"},
            {"key": "require_email_verification", "value": "true"},
            {"key": "session_timeout_minutes", "value": "2880"},
        ],
    )


def downgrade() -> None:
    op.drop_table("system_settings")

"""create_users

Revision ID: ebb0ce687a72
Revises: aaf7d7fc28f5
Create Date: 2026-05-17 21:32:19.751489

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ebb0ce687a72'
down_revision: Union[str, Sequence[str], None] = 'aaf7d7fc28f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


role_enum = postgresql.ENUM(
    'global_admin', 'organizer', 'voter', 'auditor',
    name='role',
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    role_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'users',
        sa.Column(
            'id',
            sa.UUID(),
            server_default=sa.text('gen_random_uuid()'),
            nullable=False,
        ),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.Text(), nullable=False),
        sa.Column('role', role_enum, nullable=False),
        sa.Column('is_confirmed', sa.Boolean(), nullable=False),
        sa.Column('confirmation_token', sa.String(length=128), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('confirmation_token'),
        sa.UniqueConstraint('email'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('users')
    role_enum.drop(op.get_bind(), checkfirst=True)

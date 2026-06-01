"""fix genesis entry hash

Revision ID: c4d5e6f7a8b9
Revises: b7c8d9e0f1a2
Create Date: 2026-06-01 00:00:00.000000

Recomputes the genesis audit_log entry_hash using the canonical
_compute_entry_hash algorithm so that verify-chain returns {status: "ok"}
on existing databases that were seeded with the old hardcoded hash.
"""
import hashlib
import json
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _genesis_hash() -> str:
    payload = {
        "action": "GENESIS",
        "actor_id": None,
        "data": None,
        "previous_hash": "0" * 64,
    }
    serialized = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode()).hexdigest()


def upgrade() -> None:
    op.execute(
        text(
            "UPDATE audit_log "
            "SET entry_hash = :h "
            "WHERE action = 'GENESIS' AND previous_hash = :z"
        ).bindparams(h=_genesis_hash(), z="0" * 64)
    )


def downgrade() -> None:
    pass

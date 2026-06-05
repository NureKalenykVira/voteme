"""fix audit chain — re-run the full chain rebuild over all rows

Revision ID: b2c3d4e5f6a7
Revises: f1a2b3c4
Create Date: 2026-06-05 00:00:00.000000

Re-runs the same ordered rebuild performed by migration
e5f6a7b8c9d0_rebuild_audit_chain.  That earlier migration ran when
audit_log held only the genesis row (id=1); rows id>=2 were later
inserted by old code with incorrect hashes, breaking the chain at
id=2.  This migration recomputes previous_hash and entry_hash for
every row (currently 65) using the canonical _compute_hash algorithm.
"""
import hashlib
import json
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _compute_hash(
    action: str,
    actor_id,  # uuid.UUID | str | None — normalised below
    data,      # dict | str | None     — normalised below
    previous_hash: str,
) -> str:
    """Canonical hash function — must stay byte-for-byte identical to
    AuditRepository._compute_entry_hash in audit_repository.py."""
    # Normalise actor_id: replicate the `str(actor_id) if actor_id else None`
    # logic from _compute_entry_hash.  psycopg2 may return UUID objects or
    # plain strings depending on codec registration; str() is safe for both.
    actor_str = str(actor_id) if actor_id is not None else None

    # Normalise data: JSONB columns come back as Python dicts via psycopg2
    # when the default JSON codec is registered.  Guard for the rare str case.
    if isinstance(data, str):
        data_dict = json.loads(data)
    else:
        data_dict = data  # dict or None — pass through as-is

    payload = {
        "action": action,
        "actor_id": actor_str,
        "data": data_dict,
        "previous_hash": previous_hash,
    }
    serialized = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode()).hexdigest()


def upgrade() -> None:
    conn = op.get_bind()

    rows = conn.execute(
        text("SELECT id, action, actor_id, data FROM audit_log ORDER BY id")
    ).fetchall()

    prev_hash = "0" * 64

    for row in rows:
        entry_hash = _compute_hash(row.action, row.actor_id, row.data, prev_hash)

        conn.execute(
            text(
                "UPDATE audit_log "
                "SET previous_hash = :ph, entry_hash = :eh "
                "WHERE id = :id"
            ).bindparams(ph=prev_hash, eh=entry_hash, id=row.id)
        )

        prev_hash = entry_hash


def downgrade() -> None:
    # Chain rebuild is not reversible in a meaningful way.
    # The previous state (broken chain) is not worth restoring.
    pass

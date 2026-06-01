from eth_utils import keccak


def build_merkle_root(leaves: list[bytes]) -> bytes:
    """
    Binary Merkle tree over pre-hashed 32-byte leaves.

    Pairs are positional (left + right), not sorted — leaf order is the
    caller's responsibility.  Odd-length levels duplicate the last leaf.
    Empty input returns 32 zero bytes.

    Args:
        leaves: Already-computed keccak256 hashes (32 bytes each).
                Do NOT pass raw data here — hash it before calling.

    Returns:
        32-byte Merkle root.
    """
    if not leaves:
        return b"\x00" * 32

    level: list[bytes] = list(leaves)

    while len(level) > 1:
        if len(level) % 2 == 1:
            # Duplicate the last element so every pair is complete
            level.append(level[-1])

        next_level: list[bytes] = []
        for i in range(0, len(level), 2):
            combined: bytes = level[i] + level[i + 1]
            next_level.append(keccak(primitive=combined))

        level = next_level

    return level[0]


def build_merkle_proof(leaves: list[bytes], leaf_index: int) -> list[bytes]:
    """
    Generate Merkle inclusion proof for leaf at leaf_index.
    Returns sibling hashes from leaf level up to (not including) root.
    Same padding: odd level → duplicate last leaf.
    Raises IndexError if leaf_index out of range.
    """
    if leaf_index < 0 or leaf_index >= len(leaves):
        raise IndexError(f"leaf_index {leaf_index} out of range for {len(leaves)} leaves")

    level: list[bytes] = list(leaves)
    idx = leaf_index
    proof: list[bytes] = []

    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])

        if idx % 2 == 0:
            sibling = level[idx + 1]
        else:
            sibling = level[idx - 1]
        proof.append(sibling)

        next_level: list[bytes] = []
        for i in range(0, len(level), 2):
            combined: bytes = level[i] + level[i + 1]
            next_level.append(keccak(primitive=combined))

        level = next_level
        idx = idx // 2

    return proof


def compute_root_from_proof(leaf: bytes, proof: list[bytes], leaf_index: int) -> bytes:
    """Recompute Merkle root from a leaf and its inclusion proof."""
    current = leaf
    idx = leaf_index

    for sibling in proof:
        if idx % 2 == 0:
            current = keccak(primitive=current + sibling)
        else:
            current = keccak(primitive=sibling + current)
        idx = idx // 2

    return current

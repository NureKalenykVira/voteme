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

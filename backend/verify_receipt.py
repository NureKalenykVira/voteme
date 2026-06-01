#!/usr/bin/env python3
"""
Standalone Merkle receipt verifier for VoteMe.

Anyone can run this locally, without trusting the server, to confirm that a
vote receipt is included in the official tally:

    python verify_receipt.py receipt.json

It reconstructs the Merkle root from the receipt's leaf and inclusion proof
using the exact same algorithm as the backend (app/utils/merkle.py) and
compares it to the expected root recorded in the receipt.

Only dependency is eth_utils (for keccak256). No app/* imports.
"""
import json
import sys

from eth_utils import keccak


def verify(receipt: dict) -> bool:
    # leaf = keccak256(commitment bytes) — same as build_merkle_root leaves
    leaf = keccak(primitive=bytes.fromhex(receipt["commitment"][2:]))

    # Walk the inclusion proof up to the root, same as compute_root_from_proof.
    current = leaf
    idx = receipt["leaf_index"]
    for sibling_hex in receipt["merkle_proof"]:
        sibling = bytes.fromhex(sibling_hex[2:])
        if idx % 2 == 0:
            current = keccak(primitive=current + sibling)
        else:
            current = keccak(primitive=sibling + current)
        idx //= 2

    expected = bytes.fromhex(receipt["expected_root"][2:])
    return current == expected


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python verify_receipt.py <receipt.json>")
        return 1

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        receipt = json.load(f)

    if verify(receipt):
        print("Valid ✓ — your vote is included in the official tally")
    else:
        print("Invalid ✗ — root mismatch")

    etherscan_url = receipt.get("etherscan_url")
    if etherscan_url:
        print(
            "To verify the official root was published on-chain, open this "
            "transaction in your browser and compare the recorded root:"
        )
        print(f"  {etherscan_url}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

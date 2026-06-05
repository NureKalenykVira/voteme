import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Optional

from eth_account import Account
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Optional[AsyncWeb3] = None
_initialized: bool = False
_lock: asyncio.Lock = asyncio.Lock()

_abi_cache: Optional[list] = None
_abi_lock: asyncio.Lock = asyncio.Lock()

_ABI_PATH = Path(__file__).resolve().parents[2] / "contracts" / "abi" / "VoteRegistry.json"

_DEFAULT_GAS_LIMIT = 300_000
_TX_NONCE_LOCK: asyncio.Lock = asyncio.Lock()


async def get_client() -> Optional[AsyncWeb3]:
    """Lazy-init AsyncWeb3 singleton. Returns None in disabled mode."""
    global _client, _initialized

    if _initialized:
        return _client

    async with _lock:
        if _initialized:
            return _client

        required = {
            "sepolia_rpc_url": settings.sepolia_rpc_url,
            "contract_address": settings.contract_address,
            "backend_private_key": settings.backend_private_key,
        }
        missing = [name for name, value in required.items() if not value]

        if missing:
            logger.warning(
                "Blockchain client is DISABLED. Missing env vars: %s. "
                "All blockchain operations will be skipped.",
                ", ".join(missing),
            )
            _initialized = True
            _client = None
            return None

        _client = AsyncWeb3(AsyncHTTPProvider(settings.sepolia_rpc_url))
        _initialized = True
        logger.info(
            "Blockchain client initialized (rpc=%s, contract=%s).",
            settings.sepolia_rpc_url,
            settings.contract_address,
        )
        return _client


async def is_enabled() -> bool:
    """Return True only when the blockchain client is available and configured."""
    return await get_client() is not None


async def _load_abi() -> Optional[list]:
    global _abi_cache
    if _abi_cache is not None:
        return _abi_cache
    async with _abi_lock:
        if _abi_cache is not None:
            return _abi_cache
        try:
            with _ABI_PATH.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
            abi = raw.get("abi") if isinstance(raw, dict) else raw
            if not isinstance(abi, list):
                logger.error("VoteRegistry ABI is malformed at %s", _ABI_PATH)
                return None
            _abi_cache = abi
            return _abi_cache
        except FileNotFoundError:
            logger.error("VoteRegistry ABI not found at %s", _ABI_PATH)
            return None
        except Exception as exc:
            logger.error("Failed to load VoteRegistry ABI: %s", exc)
            return None


def election_id_to_uint256(election_uuid: uuid.UUID) -> int:
    """Convert UUID election id to uint256 (big-endian, deterministic)."""
    return int.from_bytes(election_uuid.bytes, "big")


async def _send_signed_tx(
    *,
    function_name: str,
    contract_function: Any,
    w3: AsyncWeb3,
) -> Optional[str]:
    """Build, sign, send a contract tx. Returns tx hash hex or None. Never raises."""
    try:
        account = Account.from_key(settings.backend_private_key)
        sender = account.address
        chain_id = await w3.eth.chain_id

        async with _TX_NONCE_LOCK:
            nonce = await w3.eth.get_transaction_count(sender)
            try:
                gas_price = await w3.eth.gas_price
            except Exception:
                gas_price = None

            tx_params: dict = {
                "from": sender,
                "nonce": nonce,
                "gas": _DEFAULT_GAS_LIMIT,
                "chainId": chain_id,
            }
            if gas_price is not None:
                tx_params["gasPrice"] = gas_price

            tx = await contract_function.build_transaction(tx_params)
            signed = Account.sign_transaction(tx, settings.backend_private_key)
            raw_tx = getattr(signed, "raw_transaction", None) or getattr(
                signed, "rawTransaction", None
            )
            if raw_tx is None:
                logger.error(
                    "Signed tx missing raw_transaction attribute for %s", function_name
                )
                return None
            tx_hash = await w3.eth.send_raw_transaction(raw_tx)

        tx_hash_hex = tx_hash.hex()
        if not tx_hash_hex.startswith("0x"):
            tx_hash_hex = "0x" + tx_hash_hex
        logger.info(
            "Blockchain tx submitted: function=%s tx_hash=%s", function_name, tx_hash_hex
        )
        return tx_hash_hex
    except Exception as exc:
        logger.error(
            "Blockchain tx failed for %s: %s", function_name, exc, exc_info=True
        )
        return None


async def _get_contract():
    w3 = await get_client()
    if w3 is None:
        return None
    abi = await _load_abi()
    if abi is None:
        return None
    try:
        checksum = AsyncWeb3.to_checksum_address(settings.contract_address)
    except Exception as exc:
        logger.error("Invalid contract_address: %s", exc)
        return None
    return w3, w3.eth.contract(address=checksum, abi=abi)


async def publish_election(election_id: int, params_hash: bytes) -> Optional[str]:
    """Submit ElectionPublished tx. Returns tx hash or None. Never raises."""
    if len(params_hash) != 32:
        logger.error("publish_election: params_hash must be 32 bytes, got %d", len(params_hash))
        return None
    bundle = await _get_contract()
    if bundle is None:
        return None
    w3, contract = bundle
    fn = contract.functions.publishElection(election_id, params_hash)
    return await _send_signed_tx(function_name="publishElection", contract_function=fn, w3=w3)


async def commit_vote_on_chain(election_id: int, commitment_hex: str) -> Optional[str]:
    """Submit commitVote tx. commitment_hex is 64-char hex (no 0x prefix). Returns tx hash or None."""
    try:
        normalized = commitment_hex[2:] if commitment_hex.startswith("0x") else commitment_hex
        commitment_bytes = bytes.fromhex(normalized)
    except ValueError as exc:
        logger.error("commit_vote_on_chain: invalid commitment hex: %s", exc)
        return None
    if len(commitment_bytes) != 32:
        logger.error(
            "commit_vote_on_chain: commitment must decode to 32 bytes, got %d",
            len(commitment_bytes),
        )
        return None
    bundle = await _get_contract()
    if bundle is None:
        return None
    w3, contract = bundle
    fn = contract.functions.commitVote(election_id, commitment_bytes)
    return await _send_signed_tx(function_name="commitVote", contract_function=fn, w3=w3)


async def finalize_election_on_chain(
    election_id: int, merkle_root: bytes, results_hash: bytes
) -> Optional[str]:
    """Submit finalizeElection tx. Returns tx hash or None. Never raises."""
    if len(merkle_root) != 32 or len(results_hash) != 32:
        logger.error(
            "finalize_election_on_chain: bytes32 args required (merkle=%d, results=%d)",
            len(merkle_root),
            len(results_hash),
        )
        return None
    bundle = await _get_contract()
    if bundle is None:
        return None
    w3, contract = bundle
    fn = contract.functions.finalizeElection(election_id, merkle_root, results_hash)
    return await _send_signed_tx(function_name="finalizeElection", contract_function=fn, w3=w3)

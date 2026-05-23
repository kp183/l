"""API key generation and hashing utilities.

Raw keys are never stored — only the SHA-256 hex digest is persisted.
"""

from __future__ import annotations

import hashlib
import secrets

_PREFIX = "al_live_"
_PREFIX_DISPLAY_LEN = 16  # characters shown in the UI


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key and return ``(raw_key, sha256_hex_hash)``.

    The raw key is returned exactly once and must be shown to the user
    immediately.  Only the hash is stored in the database.

    Format: ``al_live_<32-byte-urlsafe-token>``
    """
    token = secrets.token_urlsafe(32)
    raw_key = f"{_PREFIX}{token}"
    key_hash = _hash_key(raw_key)
    return raw_key, key_hash


def hash_api_key(raw_key: str) -> str:
    """Return the SHA-256 hex digest of *raw_key*."""
    return _hash_key(raw_key)


def get_key_prefix(key: str) -> str:
    """Return the first 16 characters of *key* for display purposes."""
    return key[:_PREFIX_DISPLAY_LEN]


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

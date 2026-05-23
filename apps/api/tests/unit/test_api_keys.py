"""Unit tests for API key generation and hashing."""

from __future__ import annotations

import hashlib

import pytest

from app.services.api_keys import generate_api_key, get_key_prefix, hash_api_key


def test_key_starts_with_prefix() -> None:
    raw_key, _ = generate_api_key()
    assert raw_key.startswith("al_live_"), f"Expected 'al_live_' prefix, got: {raw_key[:16]}"


def test_key_minimum_length() -> None:
    raw_key, _ = generate_api_key()
    assert len(raw_key) >= 40, f"Key too short: {len(raw_key)} chars"


def test_hash_is_sha256_hex() -> None:
    raw_key, key_hash = generate_api_key()
    assert len(key_hash) == 64, f"Expected 64-char hex digest, got {len(key_hash)}"
    assert all(c in "0123456789abcdef" for c in key_hash), "Hash is not lowercase hex"


def test_hash_matches_sha256() -> None:
    raw_key, key_hash = generate_api_key()
    expected = hashlib.sha256(raw_key.encode()).hexdigest()
    assert key_hash == expected


def test_prefix_is_16_chars() -> None:
    raw_key, _ = generate_api_key()
    prefix = get_key_prefix(raw_key)
    assert len(prefix) == 16, f"Expected 16-char prefix, got {len(prefix)}"
    assert prefix == raw_key[:16]


def test_two_keys_are_unique() -> None:
    key1, hash1 = generate_api_key()
    key2, hash2 = generate_api_key()
    assert key1 != key2, "Two generated keys must be different"
    assert hash1 != hash2, "Two generated hashes must be different"


def test_hash_api_key_is_deterministic() -> None:
    raw_key, _ = generate_api_key()
    assert hash_api_key(raw_key) == hash_api_key(raw_key)


def test_hash_api_key_matches_generate() -> None:
    raw_key, key_hash = generate_api_key()
    assert hash_api_key(raw_key) == key_hash

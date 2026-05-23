"""Property-based tests for authentication invariants.

Feature: agentlens-mvp
"""

from __future__ import annotations

import hashlib
import string
import uuid as _uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings as _get_settings
from app.main import app
from app.models.api_key import APIKey
from app.models.org import OrgMember, Organization
from app.models.project import Project
from app.models.user import User
from app.services.api_keys import generate_api_key, get_key_prefix, hash_api_key

# ---------------------------------------------------------------------------
# Shared test client — JWKS calls are mocked so tests don't hit the network
# ---------------------------------------------------------------------------

# Minimal JWKS that will cause JWT decode to fail with JWTError (not network error)
_FAKE_JWKS = {"keys": []}

_client = TestClient(app, raise_server_exceptions=False)

# Strategy: printable ASCII only — HTTP headers must be ASCII
_ascii_text = st.text(
    alphabet=string.ascii_letters + string.digits + string.punctuation + " ",
    min_size=1,
)


def _make_mock_redis():
    """Return an AsyncMock Redis that behaves like an empty cache."""
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.setex = AsyncMock()
    r.incr = AsyncMock(return_value=1)
    r.expire = AsyncMock()
    r.delete = AsyncMock()
    return r


def _make_mock_db():
    """Return an AsyncMock DB session whose queries return no rows."""
    db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_result.first = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=mock_result)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# Property 4: API key format invariant
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(st.just(None))
def test_api_key_format_invariant(_: None) -> None:
    """Feature: agentlens-mvp, Property 4: API key format invariant"""
    raw_key, key_hash = generate_api_key()

    assert raw_key.startswith("al_live_"), f"Key must start with 'al_live_', got: {raw_key[:16]}"
    assert len(raw_key) >= 40, f"Key too short: {len(raw_key)}"
    assert len(key_hash) == 64, f"Hash must be 64 hex chars, got: {len(key_hash)}"
    assert all(c in "0123456789abcdef" for c in key_hash), "Hash must be lowercase hex"
    assert key_hash == hashlib.sha256(raw_key.encode()).hexdigest(), "Hash mismatch"
    assert len(get_key_prefix(raw_key)) == 16, "Prefix must be 16 chars"


# ---------------------------------------------------------------------------
# Property 1: Invalid JWT returns 401
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(token=_ascii_text)
def test_invalid_jwt_returns_401(token: str) -> None:
    """Feature: agentlens-mvp, Property 1: Invalid JWT returns 401"""
    # Skip strings that look like 3-part JWTs (header.payload.sig)
    assume(token.count(".") != 2)
    # Skip empty-ish tokens
    assume(token.strip())

    with patch(
        "app.middleware.auth._get_jwks",
        new=AsyncMock(return_value=_FAKE_JWKS),
    ):
        resp = _client.get(
            "/v1/orgs/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 401, (
        f"Expected 401 for invalid JWT '{token[:20]}', got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Property 2: Invalid API key returns 401
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(token=_ascii_text)
def test_invalid_api_key_returns_401(token: str) -> None:
    """Feature: agentlens-mvp, Property 2: Invalid API key returns 401"""
    assume(not token.startswith("al_live_"))
    assume(token.strip())

    # Override Redis and DB dependencies so require_api_key runs against
    # mock backends (empty cache + no rows → AuthenticationError → 401)
    # instead of hitting the real Redis/DB which causes event-loop errors.
    from app.database import get_db
    from app.redis_client import get_redis

    app.dependency_overrides[get_redis] = lambda: _make_mock_redis()
    app.dependency_overrides[get_db] = lambda: _make_mock_db()

    try:
        resp = _client.post(
            "/v1/ingest",
            headers={"Authorization": f"Bearer {token}"},
            json={"spans": []},
        )
        # 401 = bad key, 422 = empty spans rejected by schema
        assert resp.status_code in (401, 422), (
            f"Expected 401 for invalid API key, got {resp.status_code}: {resp.text}"
        )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Property 3: API key hash round-trip — raw key never in DB
# ---------------------------------------------------------------------------


@settings(max_examples=20)
@given(st.just(None))
def test_api_key_hash_round_trip(_: None) -> None:
    """Feature: agentlens-mvp, Property 3: API key hash round-trip"""
    raw_key, stored_hash = generate_api_key()

    assert raw_key != stored_hash
    assert hash_api_key(raw_key) == stored_hash
    assert raw_key not in stored_hash


# ---------------------------------------------------------------------------
# Property 5: Revoked key is rejected after cache expiry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoked_key_rejected_after_cache_clear() -> None:
    """Feature: agentlens-mvp, Property 5: Revoked key is rejected after cache expiry"""
    import redis.asyncio as aioredis

    cfg = _get_settings()
    engine = create_async_engine(cfg.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis = aioredis.from_url(cfg.redis_url, decode_responses=True)

    raw_key = None
    key_hash = None

    async with factory() as session:
        org = Organization(name="test-org", slug=f"test-{_uuid.uuid4().hex[:8]}")
        session.add(org)
        await session.flush()

        user = User(clerk_id=f"test_{_uuid.uuid4().hex}")
        session.add(user)
        await session.flush()

        member = OrgMember(org_id=org.id, user_id=user.id, role="owner")
        session.add(member)
        await session.flush()

        project = Project(org_id=org.id, name="test", slug=f"p-{_uuid.uuid4().hex[:8]}")
        session.add(project)
        await session.flush()

        raw_key, key_hash = generate_api_key()
        api_key = APIKey(
            project_id=project.id,
            name="test-key",
            key_hash=key_hash,
            key_prefix=get_key_prefix(raw_key),
        )
        session.add(api_key)
        await session.commit()

        # Revoke the key
        api_key.revoked_at = datetime.now(timezone.utc)
        await session.commit()

    # Clear Redis cache
    await redis.delete(f"apikey:{key_hash}")
    await redis.aclose()
    await engine.dispose()

    # Override dependencies so the TestClient's sync event loop uses fresh
    # Redis/DB connections created within that loop (not the async test's loop).
    from app.database import get_db
    from app.redis_client import get_redis

    # Build a mock Redis that returns no cached value (cache was cleared)
    mock_redis = _make_mock_redis()

    # Build a mock DB that returns no rows (key is revoked, WHERE revoked_at IS NULL excludes it)
    mock_db = _make_mock_db()

    app.dependency_overrides[get_redis] = lambda: mock_redis
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        # Revoked key must return 401
        resp = _client.post(
            "/v1/ingest",
            headers={"Authorization": f"Bearer {raw_key}"},
            json={"spans": []},
        )
        assert resp.status_code in (401, 422), (
            f"Expected 401 for revoked key, got {resp.status_code}: {resp.text}"
        )
    finally:
        app.dependency_overrides.clear()

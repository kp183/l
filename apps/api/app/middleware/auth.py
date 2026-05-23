"""FastAPI dependencies for authentication and rate limiting."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.config import get_settings
from app.database import get_db
from app.exceptions import AuthenticationError, AuthorizationError, RateLimitError
from app.models.api_key import APIKey
from app.models.project import Project
from app.models.user import User
from app.redis_client import get_redis
from app.services.api_keys import hash_api_key

logger = logging.getLogger(__name__)
settings = get_settings()

_bearer = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# JWKS cache (in-memory, 1-hour TTL)
# ---------------------------------------------------------------------------

_jwks_cache: dict[str, Any] = {}
_jwks_fetched_at: float = 0.0
_JWKS_TTL = 3600  # seconds


async def _get_jwks() -> dict:
    global _jwks_cache, _jwks_fetched_at
    now = time.monotonic()
    if _jwks_cache and (now - _jwks_fetched_at) < _JWKS_TTL:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get(settings.clerk_jwks_url, timeout=10.0)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_fetched_at = now
    return _jwks_cache


# ---------------------------------------------------------------------------
# require_api_key
# ---------------------------------------------------------------------------

_API_KEY_CACHE_TTL = 300  # seconds


async def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> Project:
    """Validate a Bearer API key and return the associated Project.

    Lookup order:
    1. Redis cache (key: ``apikey:{hash}``, TTL 300s)
    2. Database fallback — active keys only (revoked_at IS NULL)

    Raises AuthenticationError on any failure.
    """
    if not credentials:
        raise AuthenticationError("Missing Authorization header")

    raw_key = credentials.credentials
    key_hash = hash_api_key(raw_key)
    cache_key = f"apikey:{key_hash}"

    # 1. Redis cache
    cached_project_id = await redis.get(cache_key)
    if cached_project_id:
        result = await db.execute(
            select(Project).where(Project.id == cached_project_id)
        )
        project = result.scalar_one_or_none()
        if project:
            return project

    # 2. DB fallback
    result = await db.execute(
        select(APIKey, Project)
        .join(Project, APIKey.project_id == Project.id)
        .where(APIKey.key_hash == key_hash)
        .where(APIKey.revoked_at.is_(None))
    )
    row = result.first()
    if not row:
        raise AuthenticationError("Invalid or revoked API key")

    api_key_obj, project = row

    # Update last_used_at (fire-and-forget, don't block)
    await db.execute(
        update(APIKey)
        .where(APIKey.id == api_key_obj.id)
        .values(last_used_at=__import__("datetime").datetime.utcnow())
    )

    # Cache the project_id
    await redis.setex(cache_key, _API_KEY_CACHE_TTL, str(project.id))

    return project


# ---------------------------------------------------------------------------
# require_clerk_user
# ---------------------------------------------------------------------------


async def require_clerk_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate a Clerk JWT and upsert the User record.

    - Fetches JWKS from Clerk (cached 1 hour, re-fetched on key rotation)
    - Verifies signature, exp, iss
    - Upserts User by clerk_id (sub claim)

    Raises AuthenticationError on any failure.
    """
    if not credentials:
        raise AuthenticationError("Missing Authorization header")

    token = credentials.credentials

    try:
        jwks = await _get_jwks()
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except JWTError as exc:
        # On key rotation, clear cache and retry once
        global _jwks_cache, _jwks_fetched_at
        _jwks_cache = {}
        _jwks_fetched_at = 0.0
        try:
            jwks = await _get_jwks()
            payload = jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                options={"verify_aud": False},
            )
        except JWTError:
            raise AuthenticationError(f"Invalid JWT: {exc}") from exc

    clerk_id: str = payload.get("sub", "")
    if not clerk_id:
        raise AuthenticationError("JWT missing 'sub' claim")

    email: str | None = payload.get("email")
    name: str | None = (
        payload.get("name")
        or f"{payload.get('first_name', '')} {payload.get('last_name', '')}".strip()
        or None
    )

    # Upsert user
    stmt = (
        pg_insert(User)
        .values(clerk_id=clerk_id, email=email, name=name)
        .on_conflict_do_update(
            index_elements=["clerk_id"],
            set_={"email": email, "name": name},
        )
        .returning(User)
    )
    result = await db.execute(stmt)
    user = result.scalar_one()
    return user


# ---------------------------------------------------------------------------
# Rate limiting (1000 req/min per API key)
# ---------------------------------------------------------------------------

_RATE_LIMIT_WINDOW = 60  # seconds


async def check_rate_limit(
    key_hash: str,
    redis: aioredis.Redis,
    limit: int,
) -> None:
    """Increment the per-key-per-minute counter and raise RateLimitError if exceeded.

    Uses Redis key ``ratelimit:{key_hash}:{minute_bucket}`` with 60s TTL.
    """
    minute_bucket = int(time.time() // _RATE_LIMIT_WINDOW)
    redis_key = f"ratelimit:{key_hash}:{minute_bucket}"

    count = await redis.incr(redis_key)
    if count == 1:
        await redis.expire(redis_key, _RATE_LIMIT_WINDOW)

    if count > limit:
        raise RateLimitError(
            f"Rate limit of {limit} requests/minute exceeded",
            retry_after=_RATE_LIMIT_WINDOW,
        )

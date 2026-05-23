"""Async Redis connection pool and FastAPI dependency.

Uses the hiredis parser for maximum throughput.  The pool is created once
at module import time and shared across all requests.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.config import get_settings

settings = get_settings()

# ── Connection pool ───────────────────────────────────────────────────────────

_pool = aioredis.ConnectionPool.from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True,
    max_connections=20,
)

redis_client: aioredis.Redis = aioredis.Redis(connection_pool=_pool)

# ── FastAPI dependency ────────────────────────────────────────────────────────


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """Yield the shared Redis client.

    The pool manages connection lifecycle; we simply yield the client
    and let the pool handle cleanup.
    """
    yield redis_client

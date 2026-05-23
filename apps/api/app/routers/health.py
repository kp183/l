"""Health and readiness check endpoints.

/health  — lightweight liveness probe; no dependency checks.
/ready   — readiness probe; checks PostgreSQL and Redis connectivity.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.database import get_db
from app.redis_client import get_redis

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness probe — returns 200 immediately with no dependency checks."""
    return {"status": "ok", "version": "0.1.0"}


@router.get("/ready")
async def ready(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    """Readiness probe — checks PostgreSQL and Redis connectivity.

    Returns 200 when both are reachable, 503 with the failing component
    identified when either is down.
    """
    from fastapi import HTTPException

    db_status = "ok"
    redis_status = "ok"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    try:
        await redis.ping()
    except Exception:
        redis_status = "error"

    if db_status != "ok" or redis_status != "ok":
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "database": db_status,
                "redis": redis_status,
            },
        )

    return {"status": "ok", "database": "ok", "redis": "ok"}

"""Async SQLAlchemy engine, session factory, and FastAPI dependency.

Uses the asyncpg driver for all database operations.  The session is
injected into route handlers via the ``get_db`` dependency.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import text

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.database_url,
    # Pool settings suitable for a FastAPI application under moderate load.
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,   # verify connections before use
    pool_recycle=3600,    # recycle connections after 1 hour
    echo=settings.environment == "development",
)

# ── Session factory ───────────────────────────────────────────────────────────

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# ── Declarative base ──────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""

    __allow_unmapped__ = True


# ── FastAPI dependency ────────────────────────────────────────────────────────


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, rolling back on error."""
    async with AsyncSessionLocal() as session:
        # Dynamically patch execute and commit to support transparent retries
        original_execute = session.execute
        original_commit = session.commit

        async def retrying_execute(*args, **kwargs):
            return await with_db_retry(lambda: original_execute(*args, **kwargs))

        async def retrying_commit(*args, **kwargs):
            return await with_db_retry(lambda: original_commit(*args, **kwargs))

        session.execute = retrying_execute
        session.commit = retrying_commit

        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── DB retry helper ───────────────────────────────────────────────────────────

_RETRY_DELAYS = [0.1, 0.2, 0.4]


async def with_db_retry(operation, max_attempts: int = 3):
    """Run *operation* (an async callable) with exponential-backoff retry.

    Retries up to *max_attempts* times on any exception, waiting
    ``_RETRY_DELAYS[attempt]`` seconds between attempts.  Raises
    ``ServiceUnavailableError`` after all attempts are exhausted.
    """
    from app.exceptions import ServiceUnavailableError  # avoid circular import

    last_exc: Exception | None = None
    for attempt, delay in enumerate(_RETRY_DELAYS[:max_attempts]):
        try:
            return await operation()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(
                "DB operation failed (attempt %d/%d): %s",
                attempt + 1,
                max_attempts,
                exc,
            )
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)

    raise ServiceUnavailableError(
        f"Database unavailable after {max_attempts} attempts"
    ) from last_exc

"""Smoke test: verify all 7 tables and required indexes exist in the database.

Run after migrations:
    docker compose exec api pytest apps/api/tests/smoke/ -v
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()

EXPECTED_TABLES = {
    "organizations",
    "users",
    "org_members",
    "projects",
    "api_keys",
    "traces",
    "spans",
}

EXPECTED_INDEXES = {
    "idx_users_clerk_id",
    "idx_org_members_user_id",
    "idx_org_members_org_id",
    "idx_projects_org_id",
    "idx_api_keys_key_hash",
    "idx_api_keys_project_id",
    "idx_api_keys_active",
    "idx_traces_project_started",
    "idx_traces_status",
    "idx_spans_trace_started",
    "idx_spans_project_id",
    "idx_spans_tags_gin",
}


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_all_tables_exist(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )
    )
    existing = {row[0] for row in result.fetchall()}
    missing = EXPECTED_TABLES - existing
    assert not missing, f"Missing tables: {missing}"


@pytest.mark.asyncio
async def test_required_indexes_exist(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
        )
    )
    existing = {row[0] for row in result.fetchall()}
    missing = EXPECTED_INDEXES - existing
    assert not missing, f"Missing indexes: {missing}"


@pytest.mark.asyncio
async def test_spans_tags_gin_index_is_gin(db_session: AsyncSession) -> None:
    """Verify the tags index uses GIN (required for JSONB array containment)."""
    result = await db_session.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE indexname = 'idx_spans_tags_gin'"
        )
    )
    row = result.fetchone()
    assert row is not None, "idx_spans_tags_gin index not found"
    assert "gin" in row[0].lower(), f"Expected GIN index, got: {row[0]}"


@pytest.mark.asyncio
async def test_api_keys_active_is_partial_index(db_session: AsyncSession) -> None:
    """Verify the active API keys index is a partial index (WHERE revoked_at IS NULL)."""
    result = await db_session.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE indexname = 'idx_api_keys_active'"
        )
    )
    row = result.fetchone()
    assert row is not None, "idx_api_keys_active index not found"
    assert "revoked_at is null" in row[0].lower(), (
        f"Expected partial index on revoked_at IS NULL, got: {row[0]}"
    )

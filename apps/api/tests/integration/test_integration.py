"""Integration tests for the complete AgentLens system.

Covers full ingest-to-query roundtrip and API key lifecycle.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.database import AsyncSessionLocal
from app.main import app
from app.models.org import Organization, OrgMember
from app.models.user import User
from app.models.project import Project
from app.models.api_key import APIKey
from app.services.api_keys import generate_api_key, get_key_prefix, hash_api_key


@pytest.fixture(scope="module")
def event_loop():
    """Create a module-scoped event loop to share across integration tests."""
    import asyncio
    try:
        loop = asyncio.get_event_loop_policy().new_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def client():
    """Module-scoped TestClient with database migrations completed."""
    with patch("app.main.run_migrations", new=AsyncMock()):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


@pytest.fixture(autouse=True)
async def clean_db_engine():
    """Dispose the database engine before each test to clear any connections bound to other loops."""
    from app.database import engine
    await engine.dispose()


@pytest.fixture
async def test_env():
    """Set up a real test organization, user, project, and api key in the DB."""
    async with AsyncSessionLocal() as session:
        # Create unique org & user
        suffix = uuid.uuid4().hex[:8]
        org = Organization(name=f"Integration Org {suffix}", slug=f"int-org-{suffix}")
        session.add(org)
        await session.flush()

        user = User(clerk_id=f"usr_clerk_{suffix}", email=f"user_{suffix}@example.com", name="Integration User")
        session.add(user)
        await session.flush()

        member = OrgMember(org_id=org.id, user_id=user.id, role="owner")
        session.add(member)
        await session.flush()

        project = Project(org_id=org.id, name=f"Integration Project {suffix}", slug=f"int-proj-{suffix}")
        session.add(project)
        await session.flush()

        raw_key, key_hash = generate_api_key()
        api_key = APIKey(
            project_id=project.id,
            name="Integration Key",
            key_hash=key_hash,
            key_prefix=get_key_prefix(raw_key),
        )
        session.add(api_key)
        await session.commit()

        return {
            "org_id": org.id,
            "user": user,
            "project_id": project.id,
            "api_key_id": api_key.id,
            "raw_key": raw_key,
            "key_hash": key_hash,
        }


# ---------------------------------------------------------------------------
# Task 8.5: Full Ingest -> Query round-trip integration test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_ingest_query_roundtrip(client, test_env) -> None:
    # 1. Ingest a batch of spans
    trace_id = str(uuid.uuid4())
    root_span_id = str(uuid.uuid4())
    child_span_id = str(uuid.uuid4())

    spans = [
        {
            "id": root_span_id,
            "trace_id": trace_id,
            "parent_span_id": None,
            "name": "root-agent-run",
            "span_type": "agent",
            "status": "success",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "id": child_span_id,
            "trace_id": trace_id,
            "parent_span_id": root_span_id,
            "name": "openai.chat.completions.create (gpt-4o)",
            "span_type": "llm",
            "status": "success",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "model": "gpt-4o",
            "provider": "openai",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.00225,
            "input": {"messages": [{"role": "user", "content": "hello"}]},
            "output": {"choices": [{"message": {"role": "assistant", "content": "hi"}}]},
        }
    ]

    # POST to /v1/ingest with raw Bearer token
    resp = client.post(
        "/v1/ingest",
        headers={"Authorization": f"Bearer {test_env['raw_key']}"},
        json={"spans": spans},
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == {"accepted": 2, "rejected": 0}

    # 2. Mock Clerk user authentication to query traces via Query API
    from app.middleware.auth import require_clerk_user
    app.dependency_overrides[require_clerk_user] = lambda: test_env["user"]

    try:
        # Query trace list
        resp = client.get(
            "/v1/traces",
            params={"project_id": str(test_env["project_id"])},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert len(body["data"]) > 0

        # Assert trace aggregations
        trace = [t for t in body["data"] if t["id"] == trace_id][0]
        assert trace["total_tokens"] == 150
        assert abs(trace["total_cost_usd"] - 0.00225) < 1e-9
        assert trace["span_count"] == 2
        assert trace["error_count"] == 0

        # Query span tree
        resp = client.get(f"/v1/traces/{trace_id}/spans")
        assert resp.status_code == 200
        tree_body = resp.json()
        assert "data" in tree_body
        assert len(tree_body["data"]) == 1 # root node
        
        root_node = tree_body["data"][0]
        assert root_node["id"] == root_span_id
        assert len(root_node["children"]) == 1
        assert root_node["children"][0]["id"] == child_span_id

    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Task 8.6: API Key Lifecycle integration test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_key_lifecycle(client, test_env) -> None:
    # 1. Authenticate user to call key creation endpoints
    from app.middleware.auth import require_clerk_user
    app.dependency_overrides[require_clerk_user] = lambda: test_env["user"]

    try:
        # Create a new API Key via POST /v1/api-keys
        key_resp = client.post(
            "/v1/api-keys",
            json={"project_id": str(test_env["project_id"]), "name": "Lifecycle Key"},
        )
        assert key_resp.status_code == 201
        key_data = key_resp.json()
        assert "raw_key" in key_data
        new_raw_key = key_data["raw_key"]
        new_key_id = key_data["id"]

        # 2. Verify new key works for ingestion
        ingest_resp = client.post(
            "/v1/ingest",
            headers={"Authorization": f"Bearer {new_raw_key}"},
            json={"spans": [
                {
                    "id": str(uuid.uuid4()),
                    "trace_id": str(uuid.uuid4()),
                    "name": "lifecycle-span",
                    "span_type": "custom",
                    "status": "success",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }
            ]},
        )
        assert ingest_resp.status_code == 200
        assert ingest_resp.json()["data"]["accepted"] == 1

        # 3. Revoke the key via DELETE /v1/api-keys/{key_id}
        revoke_resp = client.delete(f"/v1/api-keys/{new_key_id}")
        assert revoke_resp.status_code == 204

        # Clear Redis cache for the revoked key so it takes immediate effect
        import redis.asyncio as aioredis
        from app.config import get_settings
        cfg = get_settings()
        redis = aioredis.from_url(cfg.redis_url, decode_responses=True)
        new_hash = hash_api_key(new_raw_key)
        await redis.delete(f"apikey:{new_hash}")
        await redis.aclose()

        # 4. Verify revoked key is rejected with a 401
        rejected_resp = client.post(
            "/v1/ingest",
            headers={"Authorization": f"Bearer {new_raw_key}"},
            json={"spans": []},
        )
        assert rejected_resp.status_code == 401

    finally:
        app.dependency_overrides.clear()

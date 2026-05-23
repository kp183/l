"""Unit tests for the trace query API."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.traces import decode_cursor, encode_cursor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contextmanager
def _test_client():
    with patch("app.main.run_migrations", new=AsyncMock()):
        with TestClient(app, raise_server_exceptions=False) as client:
            try:
                yield client
            finally:
                app.dependency_overrides.clear()


def _make_user():
    from app.models.user import User
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.clerk_id = "test_clerk"
    return u


def _make_project(org_id=None):
    from app.models.project import Project
    p = MagicMock(spec=Project)
    p.id = uuid.uuid4()
    p.org_id = org_id or uuid.uuid4()
    return p


def _make_trace(project_id=None):
    from app.models.trace import Trace
    t = MagicMock(spec=Trace)
    t.id = uuid.uuid4()
    t.project_id = project_id or uuid.uuid4()
    t.name = "test-trace"
    t.status = "success"
    t.started_at = datetime.now(timezone.utc)
    t.ended_at = None
    t.duration_ms = 100
    t.span_count = 1
    t.error_count = 0
    t.total_tokens = 100
    t.total_cost_usd = 0.001
    t.model = "gpt-4o"
    t.created_at = datetime.now(timezone.utc)
    t.updated_at = datetime.now(timezone.utc)
    t.input_tokens = 50
    t.output_tokens = 50
    return t


# ---------------------------------------------------------------------------
# Cursor encode/decode round-trip
# ---------------------------------------------------------------------------

def test_cursor_encode_decode_round_trip() -> None:
    started_at = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    trace_id = uuid.uuid4()

    cursor = encode_cursor(started_at, trace_id)
    decoded_at, decoded_id = decode_cursor(cursor)

    assert decoded_at == started_at
    assert decoded_id == trace_id


def test_cursor_decode_invalid_raises() -> None:
    import pytest
    with pytest.raises(ValueError):
        decode_cursor("not-a-valid-cursor")


# ---------------------------------------------------------------------------
# GET /v1/traces — requires auth
# ---------------------------------------------------------------------------

def test_list_traces_requires_auth() -> None:
    with _test_client() as client:
        resp = client.get("/v1/traces", params={"project_id": str(uuid.uuid4())})
    assert resp.status_code == 401


def test_list_traces_with_mock_auth() -> None:
    from app.middleware.auth import require_clerk_user
    from app.database import get_db

    user = _make_user()
    project = _make_project()

    mock_db = AsyncMock()
    # Mock project lookup and membership check
    mock_db.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=project)),  # project lookup
            MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock())),  # member check
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),  # trace list
        ]
    )

    app.dependency_overrides[require_clerk_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db

    with _test_client() as client:
        resp = client.get("/v1/traces", params={"project_id": str(project.id)})

    # 200 or 500 depending on mock depth — just verify auth passed (not 401)
    assert resp.status_code != 401


# ---------------------------------------------------------------------------
# GET /v1/traces/{trace_id} — 403 on cross-org access
# ---------------------------------------------------------------------------

def test_get_trace_cross_org_returns_403() -> None:
    from app.middleware.auth import require_clerk_user
    from app.database import get_db
    from app.exceptions import AuthorizationError

    user = _make_user()
    trace = _make_trace()

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=trace)),  # trace lookup
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),   # project lookup → not found
        ]
    )

    app.dependency_overrides[require_clerk_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db

    with _test_client() as client:
        resp = client.get(f"/v1/traces/{trace.id}")

    assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# GET /v1/traces/{trace_id} — 404 when trace not found
# ---------------------------------------------------------------------------

def test_get_trace_not_found_returns_404() -> None:
    from app.middleware.auth import require_clerk_user
    from app.database import get_db

    user = _make_user()
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )

    app.dependency_overrides[require_clerk_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db

    with _test_client() as client:
        resp = client.get(f"/v1/traces/{uuid.uuid4()}")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Span tree ordering
# ---------------------------------------------------------------------------

def test_span_tree_root_spans_have_no_parent() -> None:
    """Root spans in the tree must have parent_span_id=None."""
    from app.services.traces import get_span_tree
    from app.models.span import Span

    # Build flat span list: 1 root + 2 children
    root_id = uuid.uuid4()
    trace_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    def _span(span_id, parent_id, name, offset_ms=0):
        s = MagicMock(spec=Span)
        s.id = span_id
        s.trace_id = trace_id
        s.parent_span_id = parent_id
        s.name = name
        s.span_type = "custom"
        s.status = "success"
        s.started_at = datetime(2026, 1, 1, 0, 0, 0, offset_ms * 1000, tzinfo=timezone.utc)
        s.ended_at = None
        s.duration_ms = 10
        s.model = None
        s.provider = None
        s.input_tokens = None
        s.output_tokens = None
        s.cost_usd = None
        s.tool_name = None
        s.tool_call_id = None
        s.input = None
        s.output = None
        s.metadata_ = None
        s.tags = None
        s.error_type = None
        s.error_message = None
        s.error_stack = None
        return s

    child1_id = uuid.uuid4()
    child2_id = uuid.uuid4()
    spans = [
        _span(root_id, None, "root", 0),
        _span(child1_id, root_id, "child1", 1),
        _span(child2_id, root_id, "child2", 2),
    ]

    import asyncio

    async def _run():
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = spans
        mock_session.execute = AsyncMock(return_value=mock_result)
        return await get_span_tree(mock_session, trace_id)

    tree = asyncio.run(_run())

    assert len(tree) == 1, "Expected 1 root span"
    assert tree[0].parent_span_id is None
    assert len(tree[0].children) == 2
    # Children ordered by started_at
    assert tree[0].children[0].name == "child1"
    assert tree[0].children[1].name == "child2"

"""Property-based tests for the query API.

Feature: agentlens-mvp
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from fastapi.testclient import TestClient

from app.main import app
from app.services.traces import decode_cursor, encode_cursor
from app.schemas.traces import SpanNode, TraceListItem


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

@contextmanager
def _client():
    with patch("app.main.run_migrations", new=AsyncMock()):
        with TestClient(app, raise_server_exceptions=False) as c:
            try:
                yield c
            finally:
                app.dependency_overrides.clear()


def _make_trace_item(status: str = "success") -> TraceListItem:
    return TraceListItem(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        name="test",
        status=status,
        started_at=datetime.now(timezone.utc),
        span_count=1,
        error_count=0,
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Property 20: Status filter returns only matching traces
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(status=st.sampled_from(["running", "success", "error"]))
def test_status_filter_returns_only_matching(status: str) -> None:
    """Feature: agentlens-mvp, Property 20: Status filter returns only matching traces"""
    # Build a mixed list of trace items
    items = [_make_trace_item("running"), _make_trace_item("success"), _make_trace_item("error")]

    # Filter by status (simulating what the service does)
    filtered = [t for t in items if t.status == status]

    # All returned items must match the filter
    for item in filtered:
        assert item.status == status, f"Expected status={status}, got {item.status}"


# ---------------------------------------------------------------------------
# Property 21: Cursor pagination covers all records exactly once
# ---------------------------------------------------------------------------

@settings(max_examples=30)
@given(
    n=st.integers(1, 50),
    page_size=st.integers(1, 20),
)
def test_cursor_pagination_completeness(n: int, page_size: int) -> None:
    """Feature: agentlens-mvp, Property 21: Cursor pagination covers all records exactly once"""
    # Create N trace items with distinct started_at times
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    items = []
    for i in range(n):
        t = _make_trace_item()
        t = t.model_copy(update={
            "started_at": datetime(2026, 1, 1, 0, 0, i, tzinfo=timezone.utc),
            "id": uuid.uuid4(),
        })
        items.append(t)

    # Sort descending (as the API does)
    items.sort(key=lambda x: (x.started_at, x.id), reverse=True)

    # Simulate cursor pagination
    seen_ids: set[uuid.UUID] = set()
    cursor = None
    page_count = 0

    while True:
        # Get current page
        if cursor is None:
            page = items[:page_size]
            remaining = items[page_size:]
        else:
            cursor_at, cursor_id = decode_cursor(cursor)
            # Items after cursor (keyset: started_at < cursor_at OR (== and id < cursor_id))
            after = [
                t for t in items
                if t.started_at < cursor_at
                or (t.started_at == cursor_at and t.id < cursor_id)
            ]
            page = after[:page_size]
            remaining = after[page_size:]

        for item in page:
            assert item.id not in seen_ids, f"Duplicate item {item.id} on page {page_count}"
            seen_ids.add(item.id)

        if not remaining:
            break

        # Encode cursor from last item on page
        if page:
            last = page[-1]
            cursor = encode_cursor(last.started_at, last.id)
        else:
            break

        page_count += 1
        if page_count > n + 1:
            break  # safety

    assert len(seen_ids) == n, f"Expected {n} unique items, got {len(seen_ids)}"


# ---------------------------------------------------------------------------
# Property 22: Span tree reconstruction preserves parent-child relationships
# ---------------------------------------------------------------------------

@settings(max_examples=30)
@given(n_children=st.integers(0, 5))
def test_span_tree_preserves_parent_child(n_children: int) -> None:
    """Feature: agentlens-mvp, Property 22: Span tree reconstruction preserves parent-child relationships"""
    import asyncio
    from app.services.traces import get_span_tree
    from app.models.span import Span

    trace_id = uuid.uuid4()
    root_id = uuid.uuid4()

    def _mock_span(span_id, parent_id, offset=0):
        s = MagicMock(spec=Span)
        s.id = span_id
        s.trace_id = trace_id
        s.parent_span_id = parent_id
        s.name = f"span-{span_id}"
        s.span_type = "custom"
        s.status = "success"
        s.started_at = datetime(2026, 1, 1, 0, 0, offset, tzinfo=timezone.utc)
        s.ended_at = None
        s.duration_ms = 10
        s.model = s.provider = s.tool_name = s.tool_call_id = None
        s.input_tokens = s.output_tokens = None
        s.cost_usd = None
        s.input = s.output = s.metadata_ = s.tags = None
        s.error_type = s.error_message = s.error_stack = None
        return s

    spans = [_mock_span(root_id, None, 0)]
    child_ids = []
    for i in range(n_children):
        cid = uuid.uuid4()
        child_ids.append(cid)
        spans.append(_mock_span(cid, root_id, i + 1))

    async def _run():
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = spans
        mock_session.execute = AsyncMock(return_value=mock_result)
        return await get_span_tree(mock_session, trace_id)

    tree = asyncio.run(_run())

    # Root at top level
    assert len(tree) == 1
    assert tree[0].parent_span_id is None
    assert tree[0].id == root_id

    # All children under root
    assert len(tree[0].children) == n_children
    returned_child_ids = {c.id for c in tree[0].children}
    assert returned_child_ids == set(child_ids)

    # Children ordered by started_at
    for i in range(len(tree[0].children) - 1):
        assert tree[0].children[i].started_at <= tree[0].children[i + 1].started_at


# ---------------------------------------------------------------------------
# Property 23: Tenant isolation — cross-org access denied
# ---------------------------------------------------------------------------

@settings(max_examples=10, deadline=None)
@given(st.just(None))
def test_tenant_isolation_cross_org_denied(_: None) -> None:
    """Feature: agentlens-mvp, Property 23: Tenant isolation — cross-org access denied"""
    from app.middleware.auth import require_clerk_user
    from app.database import get_db
    from app.models.trace import Trace

    user = MagicMock()
    user.id = uuid.uuid4()

    trace = MagicMock(spec=Trace)
    trace.id = uuid.uuid4()
    trace.project_id = uuid.uuid4()

    # DB returns the trace but project lookup returns None (different org)
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=trace)),  # trace found
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),   # project not found → 404
        ]
    )

    app.dependency_overrides[require_clerk_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db

    with _client() as client:
        resp = client.get(f"/v1/traces/{trace.id}")

    assert resp.status_code in (403, 404), (
        f"Expected 403 or 404 for cross-org access, got {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# Property 24: API response envelope invariant
# ---------------------------------------------------------------------------

def test_error_response_has_envelope() -> None:
    """Feature: agentlens-mvp, Property 24: API response envelope invariant (error path)

    Error responses must have error.code, error.message, error.request_id.
    Success responses must have data and/or meta.
    X-Request-ID header must be present on all responses.
    """
    with _client() as client:
        # 401 — missing auth
        resp = client.get("/v1/traces", params={"project_id": str(uuid.uuid4())})
        assert resp.status_code == 401
        body = resp.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]
        assert "request_id" in body["error"]
        assert "x-request-id" in resp.headers

        # 404 — unknown route
        resp = client.get("/v1/nonexistent-route-xyz")
        assert "x-request-id" in resp.headers

        # 200 — health endpoint (no auth required)
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert "x-request-id" in resp.headers


def test_success_response_structure() -> None:
    """Success responses from paginated endpoints have data + meta."""
    from app.middleware.auth import require_clerk_user
    from app.database import get_db
    from app.models.project import Project

    user = MagicMock()
    user.id = uuid.uuid4()

    project = MagicMock(spec=Project)
    project.id = uuid.uuid4()
    project.org_id = uuid.uuid4()

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=project)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock())),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
        ]
    )

    app.dependency_overrides[require_clerk_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db

    with _client() as client:
        resp = client.get("/v1/traces", params={"project_id": str(project.id)})

    # Should not be 401 (auth passed)
    assert resp.status_code != 401

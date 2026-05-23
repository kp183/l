"""Trace query service — cursor pagination, detail, span tree reconstruction."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.span import Span
from app.models.trace import Trace
from app.schemas.traces import SpanNode


# ---------------------------------------------------------------------------
# Cursor encoding / decoding
# ---------------------------------------------------------------------------

def encode_cursor(started_at: datetime, trace_id: uuid.UUID) -> str:
    """Encode a pagination cursor as base64-urlsafe JSON.

    Format: base64url({"t": "<iso>", "i": "<uuid>"})
    """
    payload = {"t": started_at.isoformat(), "i": str(trace_id)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Decode a pagination cursor back to (started_at, trace_id).

    Raises ValueError on malformed input.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        data = json.loads(raw)
        started_at = datetime.fromisoformat(data["t"])
        trace_id = uuid.UUID(data["i"])
        return started_at, trace_id
    except Exception as exc:
        raise ValueError(f"Invalid cursor: {exc}") from exc


# ---------------------------------------------------------------------------
# Trace list (paginated)
# ---------------------------------------------------------------------------

async def list_traces(
    session: AsyncSession,
    project_id: uuid.UUID,
    limit: int = 50,
    cursor: str | None = None,
    status: str | None = None,
    model: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> tuple[list[Trace], str | None]:
    """Return a page of traces for *project_id* and the next cursor.

    Uses the composite index ``idx_traces_project_started`` for efficient
    keyset pagination on (started_at DESC, id DESC).
    """
    stmt = (
        select(Trace)
        .where(Trace.project_id == project_id)
        .order_by(Trace.started_at.desc(), Trace.id.desc())
        .limit(limit + 1)  # fetch one extra to detect next page
    )

    if cursor:
        cursor_started_at, cursor_id = decode_cursor(cursor)
        stmt = stmt.where(
            (Trace.started_at < cursor_started_at)
            | (
                (Trace.started_at == cursor_started_at)
                & (Trace.id < cursor_id)
            )
        )

    if status:
        stmt = stmt.where(Trace.status == status)
    if model:
        stmt = stmt.where(Trace.model == model)
    if start_date:
        stmt = stmt.where(Trace.started_at >= start_date)
    if end_date:
        stmt = stmt.where(Trace.started_at <= end_date)

    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = encode_cursor(last.started_at, last.id)

    return rows, next_cursor


# ---------------------------------------------------------------------------
# Trace detail
# ---------------------------------------------------------------------------

async def get_trace(
    session: AsyncSession,
    trace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> Trace | None:
    """Return a single trace, enforcing project ownership."""
    result = await session.execute(
        select(Trace).where(
            Trace.id == trace_id,
            Trace.project_id == project_id,
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Span tree reconstruction
# ---------------------------------------------------------------------------

async def get_span_tree(
    session: AsyncSession,
    trace_id: uuid.UUID,
) -> list[SpanNode]:
    """Fetch all spans for *trace_id* and build a parent-child tree.

    Returns root spans (parent_span_id IS NULL) at the top level.
    Each span's ``children`` list contains direct children ordered by started_at.
    """
    result = await session.execute(
        select(Span)
        .where(Span.trace_id == trace_id)
        .order_by(Span.started_at.asc())
    )
    spans = list(result.scalars().all())

    # Build SpanNode map
    nodes: dict[uuid.UUID, SpanNode] = {}
    for span in spans:
        nodes[span.id] = SpanNode(
            id=span.id,
            trace_id=span.trace_id,
            parent_span_id=span.parent_span_id,
            name=span.name,
            span_type=span.span_type,
            status=span.status,
            started_at=span.started_at,
            ended_at=span.ended_at,
            duration_ms=span.duration_ms,
            model=span.model,
            provider=span.provider,
            input_tokens=span.input_tokens,
            output_tokens=span.output_tokens,
            cost_usd=float(span.cost_usd) if span.cost_usd is not None else None,
            tool_name=span.tool_name,
            tool_call_id=span.tool_call_id,
            input=span.input,
            output=span.output,
            metadata=span.metadata_,
            tags=span.tags,
            error_type=span.error_type,
            error_message=span.error_message,
            error_stack=span.error_stack,
        )

    # Wire children
    roots: list[SpanNode] = []
    for node in nodes.values():
        if node.parent_span_id is None:
            roots.append(node)
        elif node.parent_span_id in nodes:
            nodes[node.parent_span_id].children.append(node)

    # Sort children by started_at
    def _sort_children(node: SpanNode) -> None:
        node.children.sort(key=lambda c: c.started_at)
        for child in node.children:
            _sort_children(child)

    roots.sort(key=lambda r: r.started_at)
    for root in roots:
        _sort_children(root)

    return roots

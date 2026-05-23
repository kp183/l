"""Ingest service — trace upsert, span bulk insert, aggregate update, pub/sub."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.models.span import Span
from app.models.trace import Trace
from app.schemas.ingest import SpanPayload

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trace upsert
# ---------------------------------------------------------------------------

async def resolve_trace(
    session: AsyncSession,
    project_id: uuid.UUID,
    span: SpanPayload,
) -> Trace | None:
    """UPSERT a Trace row for the given span.

    - Creates a new Trace on the first span for a trace_id.
    - Updates `updated_at` on subsequent spans.
    - Cross-project guard: if the trace_id already exists under a different
      project_id, returns None (caller must increment rejected count).
    """
    result = await session.execute(
        select(Trace).where(Trace.id == span.trace_id)
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        if existing.project_id != project_id:
            logger.warning(
                "Cross-project trace rejected: trace_id=%s belongs to project=%s, "
                "ingest project=%s",
                span.trace_id,
                existing.project_id,
                project_id,
            )
            return None
        # Touch updated_at
        await session.execute(
            update(Trace)
            .where(Trace.id == span.trace_id)
            .values(updated_at=datetime.now(timezone.utc))
        )
        return existing

    # Create new trace
    trace = Trace(
        id=span.trace_id,
        project_id=project_id,
        name=span.name if span.parent_span_id is None else None,
        status="running",
        started_at=span.started_at,
    )
    session.add(trace)
    await session.flush()
    return trace


# ---------------------------------------------------------------------------
# Span bulk insert
# ---------------------------------------------------------------------------

async def bulk_insert_spans(
    session: AsyncSession,
    spans: list[SpanPayload],
    project_id: uuid.UUID,
) -> int:
    """INSERT spans with ON CONFLICT (id) DO NOTHING for idempotency.

    Returns the number of rows actually inserted.
    """
    if not spans:
        return 0

    rows = [
        {
            "id": s.id,
            "trace_id": s.trace_id,
            "project_id": project_id,
            "parent_span_id": s.parent_span_id,
            "name": s.name,
            "span_type": s.span_type,
            "status": s.status,
            "started_at": s.started_at,
            "ended_at": s.ended_at,
            "duration_ms": s.duration_ms,
            "model": s.model,
            "provider": s.provider,
            "input_tokens": s.input_tokens,
            "output_tokens": s.output_tokens,
            "cost_usd": s.cost_usd,
            "tool_name": s.tool_name,
            "tool_call_id": s.tool_call_id,
            "input": s.input,
            "output": s.output,
            "metadata_": s.metadata,
            "tags": s.tags,
            "error_type": s.error_type,
            "error_message": s.error_message,
            "error_stack": s.error_stack,
        }
        for s in spans
    ]

    stmt = pg_insert(Span).values(rows).on_conflict_do_nothing(index_elements=["id"])
    result = await session.execute(stmt)
    return result.rowcount


# ---------------------------------------------------------------------------
# Trace aggregate update
# ---------------------------------------------------------------------------

async def update_trace_aggregates(
    session: AsyncSession,
    trace_id: uuid.UUID,
    spans: list[SpanPayload],
) -> None:
    """Update trace aggregates when a root span with terminal status arrives.

    Detects root span (parent_span_id IS NULL) with status 'success' or 'error'.
    Recalculates totals from all spans in the batch.
    """
    root_span = next(
        (
            s for s in spans
            if s.parent_span_id is None and s.status in ("success", "error")
        ),
        None,
    )
    if root_span is None:
        return

    total_input = sum(s.input_tokens or 0 for s in spans)
    total_output = sum(s.output_tokens or 0 for s in spans)
    total_tokens = total_input + total_output
    total_cost = sum(s.cost_usd or 0.0 for s in spans)
    error_count = sum(1 for s in spans if s.status == "error")
    span_count = len(spans)

    duration_ms = root_span.duration_ms
    if duration_ms is None and root_span.ended_at:
        delta = root_span.ended_at - root_span.started_at
        duration_ms = int(delta.total_seconds() * 1000)

    await session.execute(
        update(Trace)
        .where(Trace.id == trace_id)
        .values(
            status=root_span.status,
            ended_at=root_span.ended_at,
            duration_ms=duration_ms,
            span_count=span_count,
            error_count=error_count,
            total_tokens=total_tokens,
            input_tokens=total_input,
            output_tokens=total_output,
            total_cost_usd=total_cost,
            model=root_span.model,
        )
    )


# ---------------------------------------------------------------------------
# Redis pub/sub publish
# ---------------------------------------------------------------------------

async def publish_spans(
    redis: aioredis.Redis,
    trace_id: uuid.UUID,
    spans: list[SpanPayload],
) -> None:
    """Publish each span to the Redis channel ``trace:{trace_id}``."""
    channel = f"trace:{trace_id}"
    for span in spans:
        try:
            payload = span.model_dump_json()
            await redis.publish(channel, payload)
        except Exception:
            logger.debug("Failed to publish span %s to Redis", span.id, exc_info=True)

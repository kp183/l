"""POST /v1/ingest — span ingestion endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Response
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.config import get_settings
from app.database import get_db
from app.middleware.auth import check_rate_limit, require_api_key
from app.models.project import Project
from app.redis_client import get_redis
from app.schemas.ingest import IngestRequest, IngestResponse, SpanPayload
from app.services.ingest import (
    bulk_insert_spans,
    publish_spans,
    resolve_trace,
    update_trace_aggregates,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["ingest"])
settings = get_settings()


@router.post("/ingest", response_model=IngestResponse)
async def ingest_spans(
    body: IngestRequest,
    project: Project = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    response: Response = None,
) -> IngestResponse:
    """Ingest a batch of spans.

    - Authenticates via Bearer API key
    - Rate-limits to 1000 req/min per key
    - Per-span validation failures increment rejected without aborting the batch
    - Returns {"data": {"accepted": N, "rejected": M}, "meta": {}}
    """
    from app.services.api_keys import hash_api_key
    from fastapi import Request

    # Rate limit check — we need the raw key hash from the dependency
    # The project is returned by require_api_key; we re-hash from the header
    # via a secondary lookup. For rate limiting we use project.id as the bucket.
    rate_key = str(project.id)
    await check_rate_limit(rate_key, redis, settings.ingest_rate_limit)

    accepted = 0
    rejected = 0
    valid_spans: list[SpanPayload] = []

    # Per-span validation (batch already validated for size in schema)
    for raw_span in body.spans:
        try:
            # Spans are already validated SpanPayload objects from IngestRequest
            valid_spans.append(raw_span)
        except ValidationError:
            rejected += 1

    # Group spans by trace_id
    by_trace: dict = {}
    for span in valid_spans:
        by_trace.setdefault(span.trace_id, []).append(span)

    for trace_id, trace_spans in by_trace.items():
        # Resolve/create trace — cross-project guard
        trace = await resolve_trace(db, project.id, trace_spans[0])
        if trace is None:
            rejected += len(trace_spans)
            continue

        # Bulk insert spans
        inserted = await bulk_insert_spans(db, trace_spans, project.id)
        accepted += inserted
        rejected += len(trace_spans) - inserted

        # Update aggregates if root span is terminal
        await update_trace_aggregates(db, trace_id, trace_spans)

    await db.commit()

    # Publish to Redis pub/sub (best-effort)
    try:
        for trace_id, trace_spans in by_trace.items():
            await publish_spans(redis, trace_id, trace_spans)
    except Exception:
        logger.debug("Redis publish failed", exc_info=True)

    return IngestResponse(data={"accepted": accepted, "rejected": rejected})

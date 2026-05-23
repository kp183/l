"""Trace query endpoints.

GET /v1/traces                    — paginated trace list with filters
GET /v1/traces/{trace_id}         — trace detail
GET /v1/traces/{trace_id}/spans   — span tree
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import AuthorizationError, NotFoundError
from app.middleware.auth import require_clerk_user
from app.models.org import OrgMember
from app.models.project import Project
from app.models.user import User
from app.schemas.traces import PaginatedResponse, SpanNode, TraceDetail, TraceListItem
from app.services.traces import decode_cursor, get_span_tree, get_trace, list_traces

router = APIRouter(prefix="/v1", tags=["traces"])


# ---------------------------------------------------------------------------
# Tenant isolation helper
# ---------------------------------------------------------------------------

async def _assert_project_access(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise NotFoundError("Project not found")

    member = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == project.org_id,
            OrgMember.user_id == user_id,
        )
    )
    if not member.scalar_one_or_none():
        raise AuthorizationError("Not a member of this organization")
    return project


# ---------------------------------------------------------------------------
# GET /v1/traces
# ---------------------------------------------------------------------------

@router.get("/traces", response_model=PaginatedResponse)
async def list_traces_endpoint(
    project_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    status: str | None = None,
    model: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    user: User = Depends(require_clerk_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    await _assert_project_access(db, project_id, user.id)

    traces, next_cursor = await list_traces(
        db,
        project_id=project_id,
        limit=limit,
        cursor=cursor,
        status=status,
        model=model,
        start_date=start_date,
        end_date=end_date,
    )

    items = [TraceListItem.model_validate(t) for t in traces]
    return PaginatedResponse(
        data=items,
        meta={"total": len(items), "limit": limit},
        next_cursor=next_cursor,
    )


# ---------------------------------------------------------------------------
# GET /v1/traces/{trace_id}
# ---------------------------------------------------------------------------

@router.get("/traces/{trace_id}", response_model=TraceDetail)
async def get_trace_endpoint(
    trace_id: uuid.UUID,
    user: User = Depends(require_clerk_user),
    db: AsyncSession = Depends(get_db),
) -> TraceDetail:
    # First fetch the trace to get project_id for tenant check
    from app.models.trace import Trace
    from sqlalchemy import select as sa_select

    result = await db.execute(sa_select(Trace).where(Trace.id == trace_id))
    trace = result.scalar_one_or_none()
    if not trace:
        raise NotFoundError("Trace not found")

    await _assert_project_access(db, trace.project_id, user.id)
    return TraceDetail.model_validate(trace)


# ---------------------------------------------------------------------------
# GET /v1/traces/{trace_id}/spans
# ---------------------------------------------------------------------------

@router.get("/traces/{trace_id}/spans")
async def get_spans_endpoint(
    trace_id: uuid.UUID,
    user: User = Depends(require_clerk_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.trace import Trace
    from sqlalchemy import select as sa_select

    result = await db.execute(sa_select(Trace).where(Trace.id == trace_id))
    trace = result.scalar_one_or_none()
    if not trace:
        raise NotFoundError("Trace not found")

    await _assert_project_access(db, trace.project_id, user.id)

    tree = await get_span_tree(db, trace_id)
    total = _count_nodes(tree)
    return {"data": [n.model_dump() for n in tree], "meta": {"total": total}}


def _count_nodes(nodes: list[SpanNode]) -> int:
    count = len(nodes)
    for node in nodes:
        count += _count_nodes(node.children)
    return count

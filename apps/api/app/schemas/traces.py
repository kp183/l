"""Pydantic response schemas for the trace query API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Span schemas
# ---------------------------------------------------------------------------

class SpanNode(BaseModel):
    """A span with its children — used for tree reconstruction."""

    id: uuid.UUID
    trace_id: uuid.UUID
    parent_span_id: uuid.UUID | None = None
    name: str
    span_type: Literal["llm", "tool", "agent", "custom"]
    status: Literal["running", "success", "error"]
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: int | None = None
    model: str | None = None
    provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None
    input: Any | None = None
    output: Any | None = None
    metadata: dict[str, Any] | None = None
    tags: list[str] | None = None
    error_type: str | None = None
    error_message: str | None = None
    error_stack: str | None = None
    children: list[SpanNode] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# Pydantic v2 requires explicit model_rebuild for self-referential models
SpanNode.model_rebuild()


# ---------------------------------------------------------------------------
# Trace schemas
# ---------------------------------------------------------------------------

class TraceListItem(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str | None = None
    status: Literal["running", "success", "error"]
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: int | None = None
    span_count: int
    error_count: int
    total_tokens: int | None = None
    total_cost_usd: float | None = None
    model: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TraceDetail(TraceListItem):
    input_tokens: int | None = None
    output_tokens: int | None = None
    updated_at: datetime


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class PaginatedResponse(BaseModel):
    data: list[Any]
    meta: dict[str, Any] = Field(default_factory=dict)
    next_cursor: str | None = None


# ---------------------------------------------------------------------------
# Error envelope
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorEnvelope(BaseModel):
    error: ErrorDetail

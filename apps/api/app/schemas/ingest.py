"""Pydantic schemas for the ingest endpoint.

SpanPayload  — a single span submitted by the SDK
IngestRequest — a batch of up to 500 spans
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class SpanPayload(BaseModel):
    # Identity
    id: uuid.UUID
    trace_id: uuid.UUID
    parent_span_id: uuid.UUID | None = None

    # Classification
    name: str = Field(..., min_length=1, max_length=500)
    span_type: Literal["llm", "tool", "agent", "custom"]
    status: Literal["running", "success", "error"]

    # Timing
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: int | None = None

    # LLM fields
    model: str | None = None
    provider: Literal["openai", "anthropic", "google", "other"] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None

    # Tool fields
    tool_name: str | None = None
    tool_call_id: str | None = None

    # Payload
    input: Any | None = None
    output: Any | None = None
    metadata: dict[str, Any] | None = None
    tags: list[str] | None = None

    # Error fields
    error_type: str | None = None
    error_message: str | None = None
    error_stack: str | None = None


class IngestRequest(BaseModel):
    spans: list[SpanPayload] = Field(..., description="Batch of spans to ingest")

    @field_validator("spans")
    @classmethod
    def max_500_spans(cls, v: list[SpanPayload]) -> list[SpanPayload]:
        if len(v) > 500:
            raise ValueError(f"Batch size {len(v)} exceeds maximum of 500 spans")
        return v


class IngestResponse(BaseModel):
    data: dict[str, int]  # {"accepted": N, "rejected": M}
    meta: dict = Field(default_factory=dict)

"""ORM model for spans."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Span(Base):
    __tablename__ = "spans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )  # set by SDK, not auto-generated
    trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # FK to traces — note: project_id is denormalised (no FK per spec)
        nullable=False,
        index=True,
    )
    # Denormalised — no FK constraint (per design spec 4.7)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    parent_span_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    # "llm" | "tool" | "agent" | "custom"
    span_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # "running" | "success" | "error"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # LLM-specific fields
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)

    # Tool-specific fields
    tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Payload — stored as JSONB for flexible querying
    input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Error fields
    error_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_stack: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Large payload offload URL (S3/GCS) — nullable
    payload_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships — explicit primaryjoin because trace_id has no FK constraint
    trace: Mapped = relationship(
        "Trace",
        back_populates="spans",
        primaryjoin="Span.trace_id == Trace.id",
        foreign_keys="[Span.trace_id]",
    )

    __table_args__ = (
        CheckConstraint(
            "span_type IN ('llm', 'tool', 'agent', 'custom')",
            name="ck_spans_span_type",
        ),
        CheckConstraint(
            "status IN ('running', 'success', 'error')",
            name="ck_spans_status",
        ),
        # Composite index for fetching all spans in a trace ordered by time
        Index("idx_spans_trace_started", "trace_id", "started_at"),
        Index("idx_spans_project_id", "project_id"),
        # GIN index on tags for array containment queries
        Index("idx_spans_tags_gin", "tags", postgresql_using="gin"),
    )

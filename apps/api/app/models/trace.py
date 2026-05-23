"""ORM model for traces."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Trace(Base):
    __tablename__ = "traces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # "running" | "success" | "error"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Duration in milliseconds
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Aggregates (updated when root span completes)
    span_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_cost_usd: Mapped[float | None] = mapped_column(
        Numeric(12, 6), nullable=True
    )

    # Model used by the root/primary LLM span (denormalised for filtering)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped = relationship("Project", back_populates="traces")
    spans: Mapped[list] = relationship(
        "Span",
        back_populates="trace",
        primaryjoin="Trace.id == Span.trace_id",
        foreign_keys="[Span.trace_id]",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'success', 'error')",
            name="ck_traces_status",
        ),
        # Primary query index: list traces for a project ordered by start time
        Index("idx_traces_project_started", "project_id", "started_at"),
        Index("idx_traces_status", "status"),
    )

"""ORM model for API keys."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # SHA-256 hex digest of the raw key — never store the raw key
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # First 16 characters of the raw key for display purposes
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # NULL means active; non-NULL means revoked at that timestamp
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    project: Mapped = relationship("Project", back_populates="api_keys")

    __table_args__ = (
        Index("idx_api_keys_key_hash", "key_hash"),
        Index("idx_api_keys_project_id", "project_id"),
        # Partial index: only active (non-revoked) keys
        Index(
            "idx_api_keys_active",
            "key_hash",
            postgresql_where="revoked_at IS NULL",
        ),
    )

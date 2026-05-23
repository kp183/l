"""ORM models for organizations and org membership."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
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
    members: Mapped[list[OrgMember]] = relationship(
        "OrgMember", back_populates="organization", cascade="all, delete-orphan"
    )
    projects: Mapped[list] = relationship(
        "Project", back_populates="organization", cascade="all, delete-orphan"
    )


class OrgMember(Base):
    __tablename__ = "org_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default="member"
    )  # "owner" | "admin" | "member"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="members"
    )
    user: Mapped = relationship("User", back_populates="org_memberships")

    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_org_members_org_user"),
        Index("idx_org_members_user_id", "user_id"),
        Index("idx_org_members_org_id", "org_id"),
    )

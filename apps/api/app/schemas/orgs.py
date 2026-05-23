"""Pydantic schemas for organizations and projects."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Organizations ─────────────────────────────────────────────────────────────

class OrgCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")


class OrgResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Projects ──────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    org_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")


class ProjectResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    slug: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── API Keys ──────────────────────────────────────────────────────────────────

class APIKeyCreate(BaseModel):
    project_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)


class APIKeyResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    key_prefix: str
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None

    model_config = {"from_attributes": True}


class APIKeyCreatedResponse(APIKeyResponse):
    """Returned only on creation — includes the raw key (shown once)."""
    raw_key: str

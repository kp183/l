"""API key CRUD endpoints.

POST   /v1/api-keys          — create key (returns raw key once)
GET    /v1/api-keys           — list keys for a project (prefix only)
DELETE /v1/api-keys/{key_id} — revoke key
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import AuthorizationError, NotFoundError
from app.middleware.auth import require_clerk_user
from app.models.api_key import APIKey
from app.models.org import OrgMember
from app.models.project import Project
from app.models.user import User
from app.schemas.orgs import APIKeyCreate, APIKeyCreatedResponse, APIKeyResponse
from app.services.api_keys import generate_api_key, get_key_prefix

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["api-keys"])


async def _assert_project_access(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise NotFoundError("Project not found")

    member_result = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == project.org_id,
            OrgMember.user_id == user_id,
        )
    )
    if not member_result.scalar_one_or_none():
        raise AuthorizationError("Not a member of this organization")
    return project


@router.post("/api-keys", response_model=APIKeyCreatedResponse, status_code=201)
async def create_api_key(
    body: APIKeyCreate,
    user: User = Depends(require_clerk_user),
    db: AsyncSession = Depends(get_db),
) -> APIKeyCreatedResponse:
    """Generate a new API key. The raw key is returned exactly once."""
    await _assert_project_access(db, body.project_id, user.id)

    raw_key, key_hash = generate_api_key()
    prefix = get_key_prefix(raw_key)

    api_key = APIKey(
        project_id=body.project_id,
        name=body.name,
        key_hash=key_hash,
        key_prefix=prefix,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    logger.info(
        "audit",
        extra={
            "event_type": "audit",
            "action": "api_key_created",
            "user_id": str(user.id),
            "resource_id": str(api_key.id),
            "project_id": str(body.project_id),
        },
    )

    return APIKeyCreatedResponse(
        id=api_key.id,
        project_id=api_key.project_id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        revoked_at=api_key.revoked_at,
        raw_key=raw_key,
    )


@router.get("/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    project_id: uuid.UUID,
    user: User = Depends(require_clerk_user),
    db: AsyncSession = Depends(get_db),
) -> list[APIKeyResponse]:
    """List API keys for a project. Never returns the full key."""
    await _assert_project_access(db, project_id, user.id)
    result = await db.execute(
        select(APIKey).where(APIKey.project_id == project_id)
    )
    keys = result.scalars().all()
    return [APIKeyResponse.model_validate(k) for k in keys]


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: uuid.UUID,
    user: User = Depends(require_clerk_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke an API key by setting revoked_at = now()."""
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise NotFoundError("API key not found")

    await _assert_project_access(db, api_key.project_id, user.id)

    api_key.revoked_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info(
        "audit",
        extra={
            "event_type": "audit",
            "action": "api_key_revoked",
            "user_id": str(user.id),
            "resource_id": str(key_id),
            "project_id": str(api_key.project_id),
        },
    )

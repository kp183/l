"""Organization and Project CRUD endpoints.

All routes require a valid Clerk JWT (require_clerk_user).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import AuthorizationError, NotFoundError
from app.middleware.auth import require_clerk_user
from app.models.org import OrgMember, Organization
from app.models.project import Project
from app.models.user import User
from app.schemas.orgs import OrgCreate, OrgResponse, ProjectCreate, ProjectResponse

router = APIRouter(prefix="/v1", tags=["orgs"])


# ── Helper ────────────────────────────────────────────────────────────────────

async def _assert_org_member(
    db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID
) -> OrgMember:
    result = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise AuthorizationError("Not a member of this organization")
    return member


# ── Organizations ─────────────────────────────────────────────────────────────

@router.post("/orgs", response_model=OrgResponse, status_code=201)
async def create_org(
    body: OrgCreate,
    user: User = Depends(require_clerk_user),
    db: AsyncSession = Depends(get_db),
) -> OrgResponse:
    org = Organization(name=body.name, slug=body.slug)
    db.add(org)
    await db.flush()  # get org.id before adding member

    member = OrgMember(org_id=org.id, user_id=user.id, role="owner")
    db.add(member)
    await db.commit()
    await db.refresh(org)
    return OrgResponse.model_validate(org)


@router.get("/orgs/{org_id}", response_model=OrgResponse)
async def get_org(
    org_id: uuid.UUID,
    user: User = Depends(require_clerk_user),
    db: AsyncSession = Depends(get_db),
) -> OrgResponse:
    await _assert_org_member(db, org_id, user.id)
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise NotFoundError("Organization not found")
    return OrgResponse.model_validate(org)


@router.get("/orgs", response_model=list[OrgResponse])
async def list_orgs(
    user: User = Depends(require_clerk_user),
    db: AsyncSession = Depends(get_db),
) -> list[OrgResponse]:
    result = await db.execute(
        select(Organization)
        .join(OrgMember, OrgMember.org_id == Organization.id)
        .where(OrgMember.user_id == user.id)
    )
    orgs = result.scalars().all()
    return [OrgResponse.model_validate(o) for o in orgs]


# ── Projects ──────────────────────────────────────────────────────────────────

@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    user: User = Depends(require_clerk_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    await _assert_org_member(db, body.org_id, user.id)
    project = Project(org_id=body.org_id, name=body.name, slug=body.slug)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    org_id: uuid.UUID,
    user: User = Depends(require_clerk_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    await _assert_org_member(db, org_id, user.id)
    result = await db.execute(
        select(Project).where(Project.org_id == org_id)
    )
    projects = result.scalars().all()
    return [ProjectResponse.model_validate(p) for p in projects]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    user: User = Depends(require_clerk_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise NotFoundError("Project not found")
    await _assert_org_member(db, project.org_id, user.id)
    return ProjectResponse.model_validate(project)

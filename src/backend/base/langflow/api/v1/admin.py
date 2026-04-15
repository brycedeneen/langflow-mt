"""Platform-admin endpoints: org and membership administration across all orgs.

Every endpoint here is gated by `PlatformAdmin` (see core.py). None of these
endpoints use `CurrentOrg` — they intentionally operate outside any single
org's membership scope.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import func, select

from langflow.api.utils.core import DbSession, PlatformAdmin
from langflow.services.database.models.membership.model import Membership
from langflow.services.database.models.organization.model import Organization

router = APIRouter(prefix="/admin", tags=["Admin"])


class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9][a-z0-9-]*$")


class OrgSummary(BaseModel):
    id: UUID
    name: str
    slug: str
    is_personal: bool
    member_count: int
    created_at: str
    updated_at: str


class OrgListResponse(BaseModel):
    items: list[OrgSummary]
    total: int


@router.get("/organizations", response_model=OrgListResponse)
async def list_organizations(
    _admin: PlatformAdmin,
    session: DbSession,
    q: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OrgListResponse:
    stmt = select(Organization)
    count_stmt = select(func.count()).select_from(Organization)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Organization.name.ilike(like)) | (Organization.slug.ilike(like)))
        count_stmt = count_stmt.where(
            (Organization.name.ilike(like)) | (Organization.slug.ilike(like))
        )
    stmt = stmt.order_by(Organization.created_at).offset(offset).limit(limit)
    orgs = (await session.exec(stmt)).all()
    total = (await session.exec(count_stmt)).one()

    items: list[OrgSummary] = []
    for o in orgs:
        mc = (await session.exec(
            select(func.count()).select_from(Membership).where(Membership.organization_id == o.id)
        )).one()
        items.append(
            OrgSummary(
                id=o.id,
                name=o.name,
                slug=o.slug,
                is_personal=o.is_personal,
                member_count=int(mc),
                created_at=o.created_at.isoformat(),
                updated_at=o.updated_at.isoformat(),
            )
        )
    return OrgListResponse(items=items, total=int(total))


class MemberRow(BaseModel):
    user_id: UUID
    username: str
    role: str


class OrgDetail(BaseModel):
    id: UUID
    name: str
    slug: str
    is_personal: bool
    created_at: str
    updated_at: str
    members: list[MemberRow]


@router.get("/organizations/{org_id}", response_model=OrgDetail)
async def get_organization(
    org_id: UUID,
    _admin: PlatformAdmin,
    session: DbSession,
) -> OrgDetail:
    from langflow.services.database.models.user.model import User

    org = await session.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    rows = (await session.exec(
        select(Membership, User)
        .join(User, Membership.user_id == User.id)
        .where(Membership.organization_id == org_id)
    )).all()
    members = [
        MemberRow(user_id=u.id, username=u.username, role=m.role.value)
        for (m, u) in rows
    ]
    return OrgDetail(
        id=org.id,
        name=org.name,
        slug=org.slug,
        is_personal=org.is_personal,
        created_at=org.created_at.isoformat(),
        updated_at=org.updated_at.isoformat(),
        members=members,
    )


@router.post("/organizations", response_model=OrgSummary, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrgCreate,
    _admin: PlatformAdmin,
    session: DbSession,
) -> OrgSummary:
    org = Organization(name=body.name, slug=body.slug, is_personal=False)
    session.add(org)
    try:
        await session.flush()
    except IntegrityError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug already in use") from e
    return OrgSummary(
        id=org.id,
        name=org.name,
        slug=org.slug,
        is_personal=org.is_personal,
        member_count=0,
        created_at=org.created_at.isoformat(),
        updated_at=org.updated_at.isoformat(),
    )

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
from sqlalchemy import delete as sa_delete
from sqlalchemy.exc import IntegrityError
from sqlmodel import func, select

from langflow.api.utils.core import DbSession, PlatformAdmin
from langflow.services.database.models.membership.model import Membership
from langflow.services.database.models.organization.model import Organization

router = APIRouter(tags=["Admin"])


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


class OrgDeleteBody(BaseModel):
    confirm_name: str


class OrgDeleteResult(BaseModel):
    deleted: dict[str, int]


@router.delete("/organizations/{org_id}", response_model=OrgDeleteResult)
async def delete_organization(
    org_id: UUID,
    body: OrgDeleteBody,
    _admin: PlatformAdmin,
    session: DbSession,
) -> OrgDeleteResult:
    org = await session.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    if org.is_personal:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot delete a personal organization")
    if body.confirm_name != org.name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "confirm_name does not match organization name")

    # Explicit cascade — SQLite doesn't enforce FK cascades by default.
    from langflow.services.database.models.api_key.model import ApiKey
    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
    from langflow.services.database.models.file.model import File
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.flow_version.model import FlowVersion
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.database.models.jobs.model import Job
    from langflow.services.database.models.message.model import MessageTable
    from langflow.services.database.models.transactions.model import TransactionTable
    from langflow.services.database.models.variable.model import Variable
    from langflow.services.database.models.vertex_builds.model import VertexBuildTable

    tables = [
        ("message", MessageTable),
        ("transaction", TransactionTable),
        ("vertex_build", VertexBuildTable),
        ("flow_version", FlowVersion),
        ("flow", Flow),
        ("file", File),
        ("variable", Variable),
        ("deployment", Deployment),
        ("deployment_provider_account", DeploymentProviderAccount),
        ("job", Job),
        ("folder", Folder),
        ("api_key", ApiKey),
        ("membership", Membership),
    ]
    deleted: dict[str, int] = {}
    for label, model in tables:
        if not hasattr(model, "organization_id"):
            continue
        result = await session.exec(sa_delete(model).where(model.organization_id == org_id))
        deleted[label] = int(result.rowcount or 0)
    await session.delete(org)
    deleted["organization"] = 1
    return OrgDeleteResult(deleted=deleted)


class MemberAdd(BaseModel):
    user_id: UUID
    role: str = "owner"


class MembersResponse(BaseModel):
    items: list[MemberRow]


@router.get("/organizations/{org_id}/members", response_model=MembersResponse)
async def list_members(
    org_id: UUID,
    _admin: PlatformAdmin,
    session: DbSession,
) -> MembersResponse:
    from langflow.services.database.models.user.model import User

    if await session.get(Organization, org_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    rows = (await session.exec(
        select(Membership, User)
        .join(User, Membership.user_id == User.id)
        .where(Membership.organization_id == org_id)
    )).all()
    return MembersResponse(items=[
        MemberRow(user_id=u.id, username=u.username, role=m.role.value) for (m, u) in rows
    ])


@router.post(
    "/organizations/{org_id}/members",
    response_model=MemberRow,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    org_id: UUID,
    body: MemberAdd,
    _admin: PlatformAdmin,
    session: DbSession,
) -> MemberRow:
    from langflow.services.database.models.membership.model import MembershipRole
    from langflow.services.database.models.user.model import User

    org = await session.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    user = await session.get(User, body.user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    try:
        role = MembershipRole(body.role)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid role: {body.role}") from e

    existing = (await session.exec(
        select(Membership).where(
            Membership.user_id == user.id, Membership.organization_id == org.id
        )
    )).first()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "User already a member")
    m = Membership(user_id=user.id, organization_id=org.id, role=role)
    session.add(m)
    await session.flush()
    return MemberRow(user_id=user.id, username=user.username, role=role.value)


@router.delete(
    "/organizations/{org_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    org_id: UUID,
    user_id: UUID,
    _admin: PlatformAdmin,
    session: DbSession,
) -> None:
    org = await session.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    if org.is_personal:
        # Never orphan a user from their personal workspace.
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Cannot remove a user from their personal organization",
        )
    m = (await session.exec(
        select(Membership).where(
            Membership.user_id == user_id, Membership.organization_id == org_id
        )
    )).first()
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found")
    await session.delete(m)
    await session.flush()


class UserOrgRow(BaseModel):
    organization_id: UUID
    organization_name: str
    role: str


class UserRow(BaseModel):
    id: UUID
    username: str
    is_platform_admin: bool
    memberships: list[UserOrgRow]


class UserSearchResponse(BaseModel):
    items: list[UserRow]


@router.get("/users", response_model=UserSearchResponse)
async def search_users(
    _admin: PlatformAdmin,
    session: DbSession,
    q: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> UserSearchResponse:
    from langflow.services.database.models.user.model import User

    stmt = select(User)
    if q:
        stmt = stmt.where(User.username.ilike(f"%{q}%"))
    stmt = stmt.order_by(User.username).limit(limit)
    users = (await session.exec(stmt)).all()
    items: list[UserRow] = []
    for u in users:
        rows = (await session.exec(
            select(Membership, Organization)
            .join(Organization, Membership.organization_id == Organization.id)
            .where(Membership.user_id == u.id)
        )).all()
        items.append(
            UserRow(
                id=u.id,
                username=u.username,
                is_platform_admin=u.is_platform_admin,
                memberships=[
                    UserOrgRow(
                        organization_id=o.id,
                        organization_name=o.name,
                        role=m.role.value,
                    )
                    for (m, o) in rows
                ],
            )
        )
    return UserSearchResponse(items=items)

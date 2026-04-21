"""Router exposing the current user's org memberships.

GET /api/v1/memberships/me  — returns all memberships for the authenticated user,
joined with org info. No admin required; any active user may call this endpoint.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import select

from langflow.api.utils.core import CurrentActiveUser, DbSessionReadOnly
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization

router = APIRouter(prefix="/memberships", tags=["Memberships"])


class OrganizationSummary(BaseModel):
    id: UUID
    name: str
    slug: str
    is_personal: bool


class MyMembership(BaseModel):
    id: UUID
    role: MembershipRole
    is_org_admin: bool
    organization: OrganizationSummary

    model_config = {"from_attributes": True}


@router.get("/me", response_model=list[MyMembership])
async def list_my_memberships(
    user: CurrentActiveUser,
    session: DbSessionReadOnly,
) -> list[MyMembership]:
    stmt = (
        select(Membership, Organization)
        .join(Organization, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user.id)
        .order_by(Organization.name)
    )
    result = await session.exec(stmt)
    rows = list(result.all())
    return [
        MyMembership(
            id=m.id,
            role=m.role,
            is_org_admin=(m.role == MembershipRole.OWNER),
            organization=OrganizationSummary(
                id=o.id,
                name=o.name,
                slug=o.slug,
                is_personal=o.is_personal,
            ),
        )
        for m, o in rows
    ]

"""Platform-admin user-scoped endpoints."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlmodel import select

from langflow.api.utils.core import DbSession, PlatformAdmin
from langflow.services.database.models.membership.model import Membership
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User

router = APIRouter(tags=["Admin"])


class UserMembership(BaseModel):
    organization_id: UUID
    organization_name: str
    is_personal: bool
    role: str
    joined_at: datetime


class UserDetail(BaseModel):
    id: UUID
    username: str
    is_active: bool
    is_platform_admin: bool
    is_superuser: bool
    create_at: datetime | None = None
    updated_at: datetime | None = None
    last_login_at: datetime | None = None
    memberships: list[UserMembership]


@router.get("/users/{user_id}", response_model=UserDetail)
async def get_user_detail(
    user_id: UUID,
    _admin: PlatformAdmin,
    session: DbSession,
) -> UserDetail:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    rows = (await session.exec(
        select(Membership, Organization)
        .join(Organization, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user.id)
    )).all()
    # Personal org first, then alphabetical by org name.
    rows_sorted = sorted(rows, key=lambda r: (not r[1].is_personal, r[1].name.lower()))
    memberships = [
        UserMembership(
            organization_id=o.id,
            organization_name=o.name,
            is_personal=o.is_personal,
            role=m.role.value,
            joined_at=m.created_at,
        )
        for (m, o) in rows_sorted
    ]
    return UserDetail(
        id=user.id,
        username=user.username,
        is_active=user.is_active,
        is_platform_admin=user.is_platform_admin,
        is_superuser=user.is_superuser,
        create_at=getattr(user, "create_at", None),
        updated_at=getattr(user, "updated_at", None),
        last_login_at=getattr(user, "last_login_at", None),
        memberships=memberships,
    )

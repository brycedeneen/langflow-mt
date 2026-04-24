"""Platform-admin user-scoped endpoints."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
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
        create_at=user.create_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        memberships=memberships,
    )


class PlatformAdminUpdate(BaseModel):
    is_platform_admin: bool


@router.patch("/users/{user_id}/platform-admin", response_model=UserDetail)
async def set_user_platform_admin(
    user_id: UUID,
    body: PlatformAdminUpdate,
    admin: PlatformAdmin,
    session: DbSession,
) -> UserDetail:
    """Grant or revoke a user's platform-admin flag. Platform-admin only.

    Dedicated endpoint so the privileged flag is never accepted via the
    self-service ``PATCH /api/v1/users/{user_id}`` surface.
    """
    if user_id == admin.id and not body.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can't remove your own platform-admin role",
        )
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    if user.is_platform_admin and not body.is_platform_admin:
        remaining = (
            await session.exec(
                select(func.count())
                .select_from(User)
                .where(User.is_platform_admin == True, User.id != user_id)  # noqa: E712
            )
        ).first()
        if not remaining:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last platform admin",
            )

    user.is_platform_admin = body.is_platform_admin
    await session.flush()
    await session.refresh(user)
    return await get_user_detail(user_id=user_id, _admin=admin, session=session)

"""Org-scoped role authorization helpers.

Two entry points:
    - `require_org_role(min_role)` — FastAPI dependency factory for endpoints
      where the caller has an `org_id` path param.
    - `assert_org_role(user, org_id, min_role, session)` — imperative check,
      used by resource endpoints that resolve org_id from the resource itself.
"""
from __future__ import annotations

from typing import Annotated, Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Path
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils.core import CurrentActiveUser, DbSession
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.user.model import User


ROLE_ORDER: dict[MembershipRole, int] = {
    MembershipRole.OWNER: 5,
    MembershipRole.ADMIN: 4,
    MembershipRole.MEMBER: 3,
    MembershipRole.OPERATOR: 2,
    MembershipRole.VIEWER: 1,
}


async def _load_membership(
    session: AsyncSession, user_id: UUID, org_id: UUID
) -> Membership | None:
    stmt = select(Membership).where(
        Membership.user_id == user_id,
        Membership.organization_id == org_id,
    )
    return (await session.exec(stmt)).first()


async def assert_org_role(
    user: User,
    org_id: UUID,
    min_role: MembershipRole,
    *,
    session: AsyncSession,
) -> Membership | None:
    """Raise 403 unless caller has at least `min_role` in `org_id`.
    Platform admins bypass and receive None.
    """
    if user.is_platform_admin:
        return None
    membership = await _load_membership(session, user.id, org_id)
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    if ROLE_ORDER[membership.role] < ROLE_ORDER[min_role]:
        raise HTTPException(status_code=403, detail=f"Requires role {min_role.value} or higher")
    return membership


def require_org_role(min_role: MembershipRole) -> Callable:
    """Dep factory: FastAPI dep that reads `org_id` from the path and enforces
    `min_role`. Returns the caller's Membership (or None for platform-admin bypass).
    """
    async def _dep(
        org_id: Annotated[UUID, Path(...)],
        user: CurrentActiveUser,
        session: DbSession,
    ) -> Membership | None:
        return await assert_org_role(user, org_id, min_role, session=session)
    return _dep


OrgRoleOwner    = Annotated[Membership | None, Depends(require_org_role(MembershipRole.OWNER))]
OrgRoleAdmin    = Annotated[Membership | None, Depends(require_org_role(MembershipRole.ADMIN))]
OrgRoleMember   = Annotated[Membership | None, Depends(require_org_role(MembershipRole.MEMBER))]
OrgRoleOperator = Annotated[Membership | None, Depends(require_org_role(MembershipRole.OPERATOR))]
OrgRoleViewer   = Annotated[Membership | None, Depends(require_org_role(MembershipRole.VIEWER))]

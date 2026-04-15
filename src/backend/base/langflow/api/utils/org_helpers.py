from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils.core import CurrentActiveUser, DbSession
from langflow.services.database.models.membership.model import Membership
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User


async def get_current_organization(
    user: CurrentActiveUser,
    session: DbSession,
    x_acting_org_id: Annotated[str | None, Header(alias="X-Acting-Org-Id")] = None,
) -> Organization:
    if x_acting_org_id is not None:
        if not user.is_superuser:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "X-Acting-Org-Id requires superuser")
        try:
            org_id = UUID(x_acting_org_id)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid X-Acting-Org-Id") from e
        org = await session.get(Organization, org_id)
        if org is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
        return org

    rows = (await session.exec(select(Membership).where(Membership.user_id == user.id))).all()
    if len(rows) == 0:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User has no organization membership")
    if len(rows) > 1:
        # Slice invariant: one membership per user. If violated, fail loudly.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "User has multiple memberships (unsupported in this slice)",
        )
    org = await session.get(Organization, rows[0].organization_id)
    if org is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Membership references missing organization")
    return org


async def get_current_membership(
    user: CurrentActiveUser,
    session: DbSession,
) -> Membership:
    row = (await session.exec(select(Membership).where(Membership.user_id == user.id))).first()
    if row is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User has no organization membership")
    return row

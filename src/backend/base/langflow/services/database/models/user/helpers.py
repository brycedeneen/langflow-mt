"""Helpers for user lifecycle, including personal-org provisioning."""
from __future__ import annotations

from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User


async def resolve_user_organization_id(session: AsyncSession, user_id: UUID | str) -> UUID | None:
    """Return the organization_id of the user's (single) membership, or None.

    Intended for internal callers that don't have access to the request-scoped
    CurrentOrg dependency (background tasks, CLI paths, migration shims).
    """
    row = (
        await session.exec(select(Membership).where(Membership.user_id == user_id))
    ).first()
    return row.organization_id if row is not None else None


async def ensure_personal_organization(session: AsyncSession, user: User) -> Organization:
    """Create a personal Organization + owner Membership for a newly created user.

    Idempotent: if the user already has a membership, return that organization.
    """
    existing = (
        await session.exec(select(Membership).where(Membership.user_id == user.id))
    ).first()
    if existing is not None:
        org = await session.get(Organization, existing.organization_id)
        if org is not None:
            return org

    org = Organization(
        name=f"{user.username}'s workspace",
        slug=f"user-{user.id}",
        is_personal=True,
    )
    session.add(org)
    await session.flush()
    session.add(
        Membership(user_id=user.id, organization_id=org.id, role=MembershipRole.OWNER)
    )
    await session.flush()
    return org

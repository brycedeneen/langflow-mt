import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool

from langflow.api.utils.org_helpers import get_current_organization
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User


@pytest.fixture
async def async_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


async def _user(session, name="alice", is_superuser=False):
    u = User(username=name, password="x", is_active=True, is_superuser=is_superuser)
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u


async def _org(session, slug="acme"):
    o = Organization(name=slug, slug=slug)
    session.add(o)
    await session.commit()
    await session.refresh(o)
    return o


@pytest.fixture
async def user_with_membership(async_session):
    from sqlmodel import delete

    u = await _user(async_session, "alice")
    o = await _org(async_session, "org-a")
    # Drop any auto-provisioned membership from the after_insert hook so the fixture
    # deterministically yields a single membership in org-a.
    await async_session.exec(delete(Membership).where(Membership.user_id == u.id))
    async_session.add(Membership(user_id=u.id, organization_id=o.id, role=MembershipRole.OWNER))
    await async_session.commit()
    return u, o


@pytest.fixture
async def user_without_membership(async_session):
    from sqlmodel import delete

    u = await _user(async_session, "bob")
    # Clean up any membership the after_insert hook auto-provisioned so this user
    # is genuinely membership-less for the test.
    await async_session.exec(delete(Membership).where(Membership.user_id == u.id))
    await async_session.commit()
    return u


@pytest.fixture
async def superuser(async_session):
    return await _user(async_session, "admin", is_superuser=True)


@pytest.fixture
async def other_org(async_session):
    return await _org(async_session, "other-org")


@pytest.mark.asyncio
async def test_returns_single_membership_org(async_session, user_with_membership):
    user, org = user_with_membership
    result = await get_current_organization(user=user, session=async_session, x_acting_org_id=None)
    assert result.id == org.id


@pytest.mark.asyncio
async def test_no_membership_raises_403(async_session, user_without_membership):
    with pytest.raises(HTTPException) as exc:
        await get_current_organization(
            user=user_without_membership, session=async_session, x_acting_org_id=None
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_superuser_acting_as_with_header(async_session, superuser, other_org):
    result = await get_current_organization(
        user=superuser, session=async_session, x_acting_org_id=str(other_org.id)
    )
    assert result.id == other_org.id


@pytest.mark.asyncio
async def test_non_superuser_acting_as_rejected(async_session, user_with_membership, other_org):
    user, _ = user_with_membership
    with pytest.raises(HTTPException) as exc:
        await get_current_organization(
            user=user, session=async_session, x_acting_org_id=str(other_org.id)
        )
    assert exc.value.status_code == 403

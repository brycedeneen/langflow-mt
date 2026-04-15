import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool

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


async def _make_user(session, name="alice"):
    user = User(username=name, password="x", is_active=True)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _make_org(session, slug="acme"):
    org = Organization(name=slug, slug=slug)
    session.add(org)
    await session.commit()
    await session.refresh(org)
    return org


@pytest.mark.asyncio
async def test_create_membership(async_session):
    user = await _make_user(async_session)
    org = await _make_org(async_session)
    m = Membership(user_id=user.id, organization_id=org.id, role=MembershipRole.OWNER)
    async_session.add(m)
    await async_session.commit()
    await async_session.refresh(m)
    assert m.role == MembershipRole.OWNER


@pytest.mark.asyncio
async def test_membership_user_org_unique(async_session):
    user = await _make_user(async_session)
    org = await _make_org(async_session)
    async_session.add(Membership(user_id=user.id, organization_id=org.id))
    await async_session.commit()
    async_session.add(Membership(user_id=user.id, organization_id=org.id))
    with pytest.raises(Exception):
        await async_session.commit()

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool

from sqlmodel import delete

from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.helpers import ensure_personal_organization
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


@pytest.mark.asyncio
async def test_ensure_personal_organization_creates_org_and_membership(async_session):
    user = User(username="bob", password="x", is_active=True)
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    # Drop the auto-provisioned membership from the after_insert hook so we can
    # exercise ensure_personal_organization in isolation.
    await async_session.exec(delete(Membership).where(Membership.user_id == user.id))
    await async_session.commit()

    org = await ensure_personal_organization(async_session, user)
    await async_session.commit()

    assert org.is_personal is True
    assert org.name == "bob's workspace"

    rows = (
        await async_session.exec(select(Membership).where(Membership.user_id == user.id))
    ).all()
    assert len(rows) == 1
    assert rows[0].role == MembershipRole.OWNER
    assert rows[0].organization_id == org.id


@pytest.mark.asyncio
async def test_ensure_personal_organization_is_idempotent(async_session):
    user = User(username="alice", password="x", is_active=True)
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    await async_session.exec(delete(Membership).where(Membership.user_id == user.id))
    await async_session.commit()

    org1 = await ensure_personal_organization(async_session, user)
    await async_session.commit()
    org2 = await ensure_personal_organization(async_session, user)
    await async_session.commit()

    assert org1.id == org2.id
    rows = (
        await async_session.exec(select(Organization).where(Organization.slug == f"user-{user.id}"))
    ).all()
    assert len(rows) == 1

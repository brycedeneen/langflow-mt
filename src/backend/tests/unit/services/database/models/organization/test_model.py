import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool

from langflow.services.database.models.organization.model import Organization


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
async def test_create_organization(async_session):
    org = Organization(name="Acme", slug="acme", is_personal=False)
    async_session.add(org)
    await async_session.commit()
    await async_session.refresh(org)

    assert org.id is not None
    assert org.name == "Acme"
    assert org.slug == "acme"
    assert org.is_personal is False
    assert org.created_at is not None


@pytest.mark.asyncio
async def test_organization_slug_unique(async_session):
    async_session.add(Organization(name="A", slug="dup"))
    await async_session.commit()
    async_session.add(Organization(name="B", slug="dup"))
    with pytest.raises(Exception):
        await async_session.commit()

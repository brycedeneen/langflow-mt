from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool

from langflow.schema.serialize import UUIDstr
from langflow.services.database import scoping
from langflow.services.database.scoping import (
    MissingOrgFilterError,
    MissingOrgIdOnInsertError,
    allow_cross_org_query,
    install_scoping_guards,
)

# Test-local tenant table, added to TENANT_SCOPED_TABLES in a fixture.
_FAKE_TABLE_NAME = "fake_tenant"


# Separate metadata so FakeTenant does not register on SQLModel.metadata, which
# would leak into test_no_phantom_migrations' autogenerate diff.
class _TestModelBase(SQLModel):
    metadata = sa.MetaData()


class FakeTenant(_TestModelBase, table=True):  # type: ignore[call-arg]
    __tablename__ = _FAKE_TABLE_NAME

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    # nullable=False mirrors production schema so the DB-level constraint fires.
    organization_id: UUIDstr | None = Field(default=None, nullable=False)
    name: str = Field(default="x")


@pytest.fixture
def tenant_table_registered():
    scoping.TENANT_SCOPED_TABLES.add(_FAKE_TABLE_NAME)
    yield
    scoping.TENANT_SCOPED_TABLES.discard(_FAKE_TABLE_NAME)


@pytest.fixture
async def guarded_session(tenant_table_registered):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    install_scoping_guards(engine.sync_engine, enforce_select=True)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.run_sync(_TestModelBase.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_select_without_org_filter_raises(guarded_session):
    with pytest.raises(MissingOrgFilterError):
        await guarded_session.exec(select(FakeTenant))


@pytest.mark.asyncio
async def test_select_with_org_filter_passes(guarded_session):
    org_id = uuid4()
    result = await guarded_session.exec(
        select(FakeTenant).where(FakeTenant.organization_id == org_id)
    )
    assert result.all() == []


@pytest.mark.asyncio
async def test_allow_cross_org_query_suppresses(guarded_session):
    with allow_cross_org_query():
        result = await guarded_session.exec(select(FakeTenant))
    assert result.all() == []


@pytest.mark.asyncio
async def test_insert_without_org_id_auto_provisions_system_org(guarded_session):
    """When the guard can't resolve org from user_id/flow_id/folder_id, it falls back
    to provisioning the 'system-orphan' org so the NOT NULL constraint is satisfied."""
    row = FakeTenant(name="x")
    guarded_session.add(row)
    await guarded_session.commit()
    assert row.organization_id is not None

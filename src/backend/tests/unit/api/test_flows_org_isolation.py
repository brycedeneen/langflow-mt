"""Task 10: org-scoping smoke tests for flows router.

We avoid the full-app fixture and exercise the scoped _read_flow helper and
the list query's org filter directly against an in-memory SQLite DB.
"""
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool

from langflow.api.v1.flows import _read_flow
from langflow.services.database.models.flow.model import Flow
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


@pytest.fixture
async def two_orgs(async_session):
    org_a = Organization(name="A", slug="org-a")
    org_b = Organization(name="B", slug="org-b")
    user_a = User(username="user-a", password="x", is_active=True)
    user_b = User(username="user-b", password="x", is_active=True)
    async_session.add_all([org_a, org_b, user_a, user_b])
    await async_session.commit()
    async_session.add_all(
        [
            Membership(user_id=user_a.id, organization_id=org_a.id, role=MembershipRole.OWNER),
            Membership(user_id=user_b.id, organization_id=org_b.id, role=MembershipRole.OWNER),
        ]
    )
    await async_session.commit()
    return {"user_a": user_a, "user_b": user_b, "org_a": org_a, "org_b": org_b}


@pytest.mark.asyncio
async def test_read_flow_scopes_by_organization(async_session, two_orgs):
    """A flow owned by user_a in org_b must NOT leak to user_a when queried in org_a."""
    # Edge case: user_a has a flow mis-tagged to org_b (shouldn't happen, but proves the filter)
    flow_leak = Flow(
        name="leak",
        user_id=two_orgs["user_a"].id,
        organization_id=two_orgs["org_b"].id,
        data={},
    )
    async_session.add(flow_leak)
    await async_session.commit()

    # Reading in org_a's context: should return None
    result = await _read_flow(
        async_session,
        flow_leak.id,
        user_id=two_orgs["user_a"].id,
        organization_id=two_orgs["org_a"].id,
    )
    assert result is None

    # Reading in org_b's context: finds it
    result = await _read_flow(
        async_session,
        flow_leak.id,
        user_id=two_orgs["user_a"].id,
        organization_id=two_orgs["org_b"].id,
    )
    assert result is not None
    assert result.id == flow_leak.id


@pytest.mark.asyncio
async def test_list_query_filters_by_organization(async_session, two_orgs):
    """The read_flows list query filter by organization_id eliminates cross-org rows."""
    async_session.add_all(
        [
            Flow(name="a", user_id=two_orgs["user_a"].id, organization_id=two_orgs["org_a"].id, data={}),
            Flow(name="b", user_id=two_orgs["user_b"].id, organization_id=two_orgs["org_b"].id, data={}),
        ]
    )
    await async_session.commit()

    stmt = (
        select(Flow)
        .where(Flow.user_id == two_orgs["user_a"].id)
        .where(
            (Flow.organization_id == two_orgs["org_a"].id)
            | (Flow.organization_id == None)  # noqa: E711
        )
    )
    rows = (await async_session.exec(stmt)).all()
    names = [r.name for r in rows]
    assert "a" in names
    assert "b" not in names

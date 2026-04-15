"""Task 17: cross-org isolation matrix — personal-org mode.

Slice invariant: every user has exactly one personal Organization. Therefore
a query filtered by (user_id == caller, organization_id == caller's org)
must return no rows owned by a different user/org. We validate this
invariant across the tenant models that have an org column.
"""
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool

from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.file.model import File as UserFile
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable


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
    org_a = Organization(name="A", slug="org-a", is_personal=True)
    org_b = Organization(name="B", slug="org-b", is_personal=True)
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


@pytest.mark.parametrize(
    "model,factory",
    [
        (
            Flow,
            lambda u, o: Flow(name=f"flow-{uuid4()}", user_id=u.id, organization_id=o.id, data={}),
        ),
        (
            Folder,
            lambda u, o: Folder(name=f"proj-{uuid4()}", user_id=u.id, organization_id=o.id),
        ),
        (
            UserFile,
            lambda u, o: UserFile(
                user_id=u.id,
                organization_id=o.id,
                name=f"f-{uuid4()}",
                path=f"{u.id}/f.bin",
                size=1,
            ),
        ),
        (
            Variable,
            lambda u, o: Variable(
                name=f"v-{uuid4()}",
                value="x",
                user_id=u.id,
                organization_id=o.id,
                default_fields=[],
            ),
        ),
        (
            ApiKey,
            lambda u, o: ApiKey(
                api_key=f"key-{uuid4()}", user_id=u.id, organization_id=o.id
            ),
        ),
    ],
)
@pytest.mark.asyncio
async def test_cross_org_query_returns_empty(model, factory, two_orgs, async_session):
    # Create one row in org_b
    row_b = factory(two_orgs["user_b"], two_orgs["org_b"])
    async_session.add(row_b)
    await async_session.commit()

    # Query as user_a / org_a — should see nothing
    stmt = select(model).where(
        model.user_id == two_orgs["user_a"].id,
        model.organization_id == two_orgs["org_a"].id,
    )
    rows = (await async_session.exec(stmt)).all()
    assert rows == [], f"{model.__name__} leaked cross-org: {rows!r}"

    # Query as user_b / org_b — sees its own row
    stmt = select(model).where(
        model.user_id == two_orgs["user_b"].id,
        model.organization_id == two_orgs["org_b"].id,
    )
    rows = (await async_session.exec(stmt)).all()
    assert len(rows) == 1

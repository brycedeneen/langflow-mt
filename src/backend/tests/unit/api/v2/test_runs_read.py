from __future__ import annotations

import pytest
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from langflow.services.database.models.flow_run.model import FlowRun, RunStatus, TriggeredBy
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User


@pytest.fixture
def runs_client(monkeypatch, tmp_path):
    """Create a test client with auth/org/session dependencies overridden, seeding real FlowRun rows."""
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("LANGFLOW_SUPERUSER", "admin")
    monkeypatch.setenv("LANGFLOW_SUPERUSER_PASSWORD", "testpassword123")

    from langflow.main import create_app
    from langflow.api.utils.org_helpers import get_current_organization
    from langflow.services.auth.utils import get_current_active_user
    from lfx.services.deps import injectable_session_scope

    # Build an in-memory SQLite engine just for this test
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    import asyncio

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        sessionmaker_ = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        fake_user = User(id=uuid4(), username="tester", password="x", is_superuser=False, is_active=True)
        fake_org = Organization(
            id=uuid4(),
            name="test",
            slug="test-org",
            runs_priority_tier="default",
            runs_max_concurrent=5,
        )

        async with sessionmaker_() as session:
            session.add(fake_user)
            session.add(fake_org)
            await session.commit()
            await session.refresh(fake_user)
            await session.refresh(fake_org)

        # Seed two FlowRun rows directly (no Flow FK needed — SQLite doesn't enforce FK by default)
        run1 = FlowRun(
            id=uuid4(),
            organization_id=fake_org.id,
            flow_id=uuid4(),
            triggered_by=TriggeredBy.API,
            status=RunStatus.QUEUED,
        )
        run2 = FlowRun(
            id=uuid4(),
            organization_id=fake_org.id,
            flow_id=run1.flow_id,
            triggered_by=TriggeredBy.API,
            status=RunStatus.RUNNING,
        )

        async with sessionmaker_() as session:
            session.add(run1)
            session.add(run2)
            await session.commit()
            await session.refresh(run1)
            await session.refresh(run2)

        return fake_user, fake_org, run1, run2, sessionmaker_

    fake_user, fake_org, run1, run2, sessionmaker_ = asyncio.get_event_loop().run_until_complete(_setup())

    async def _session_override():
        async with sessionmaker_() as s:
            yield s

    app = create_app()
    app.dependency_overrides[injectable_session_scope] = _session_override
    app.dependency_overrides[get_current_active_user] = lambda: fake_user
    app.dependency_overrides[get_current_organization] = lambda: fake_org

    ctx = {
        "user": fake_user,
        "org": fake_org,
        "runs": [run1, run2],
        "flow_id": run1.flow_id,
    }

    client = TestClient(app)
    yield client, ctx

    app.dependency_overrides.clear()
    asyncio.get_event_loop().run_until_complete(engine.dispose())


def test_get_run_ok(runs_client):
    client, ctx = runs_client
    run = ctx["runs"][0]
    resp = client.get(f"/api/v2/runs/{run.id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "queued"
    assert data["id"] == str(run.id)
    assert data["organization_id"] == str(ctx["org"].id)


def test_get_run_404_other_org(runs_client):
    client, ctx = runs_client
    resp = client.get(f"/api/v2/runs/{uuid4()}")
    assert resp.status_code == 404, resp.text


def test_list_runs_by_flow(runs_client):
    client, ctx = runs_client
    resp = client.get(f"/api/v2/runs?flow_id={ctx['flow_id']}")
    assert resp.status_code == 200, resp.text
    ids = {r["id"] for r in resp.json()["items"]}
    assert ids == {str(ctx["runs"][0].id), str(ctx["runs"][1].id)}


def test_list_runs_limit(runs_client):
    client, ctx = runs_client
    resp = client.get("/api/v2/runs?limit=1")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["next_cursor"] is not None

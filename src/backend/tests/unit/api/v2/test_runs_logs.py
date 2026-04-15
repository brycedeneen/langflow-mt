from __future__ import annotations

import asyncio
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


@pytest.fixture
def runs_client(monkeypatch, tmp_path):
    """
    Logs-endpoint test fixture.

    Uses a temp-file SQLite DB so that aiosqlite creates a fresh connection per
    request (avoiding the "Future attached to a different loop" problem that
    arises when an in-memory engine's pool is shared between the fixture's
    setup loop and TestClient's background thread loop).
    """
    db_path = tmp_path / "logs_test.db"
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "true")

    from langflow.main import create_app
    from langflow.api.utils.org_helpers import get_current_organization
    from langflow.services.auth.utils import get_current_active_user
    from langflow.services.database.models.flow_run.model import FlowRun, TriggeredBy, RunStatus
    from langflow.services.database.models.flow_run_log.model import FlowRunLog, LogLevel
    from langflow.services.database.models.organization.model import Organization
    from langflow.services.database.models.user.model import User
    from lfx.services.deps import injectable_session_scope

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        fake_user = User(id=uuid4(), username="tester", password="x", is_superuser=False, is_active=True)
        fake_org = Organization(
            id=uuid4(), name="test", slug="test-org",
            runs_priority_tier="default", runs_max_concurrent=5,
        )

        async with sm() as s:
            s.add(fake_user)
            s.add(fake_org)
            await s.commit()
            await s.refresh(fake_user)
            await s.refresh(fake_org)

        run = FlowRun(
            id=uuid4(), organization_id=fake_org.id, flow_id=uuid4(),
            triggered_by=TriggeredBy.API, status=RunStatus.RUNNING,
        )

        async with sm() as s:
            s.add(run)
            await s.commit()
            await s.refresh(run)

        now = datetime.now(timezone.utc)
        async with sm() as s:
            for i in range(5):
                s.add(FlowRunLog(run_id=run.id, ts=now, level=LogLevel.INFO, message=f"m{i}"))
            await s.commit()

        return fake_user, fake_org, run, sm

    fake_user, fake_org, run, sm = asyncio.get_event_loop().run_until_complete(_setup())

    async def _session_override():
        async with sm() as s:
            yield s

    app = create_app()
    app.dependency_overrides[injectable_session_scope] = _session_override
    app.dependency_overrides[get_current_active_user] = lambda: fake_user
    app.dependency_overrides[get_current_organization] = lambda: fake_org

    ctx = {
        "engine": engine,
        "user": fake_user,
        "org": fake_org,
        "run": run,
        "sessionmaker": sm,
    }

    client = TestClient(app)
    yield client, ctx

    app.dependency_overrides.clear()
    asyncio.get_event_loop().run_until_complete(engine.dispose())


def test_logs_first_page(runs_client):
    client, ctx = runs_client
    resp = client.get(f"/api/v2/runs/{ctx['run'].id}/logs?limit=2")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] is not None


def test_logs_paginate_with_cursor(runs_client):
    client, ctx = runs_client
    resp = client.get(f"/api/v2/runs/{ctx['run'].id}/logs?limit=2")
    assert resp.status_code == 200, resp.text
    first_cursor = resp.json()["next_cursor"]
    assert first_cursor is not None

    resp2 = client.get(f"/api/v2/runs/{ctx['run'].id}/logs?limit=2&cursor={first_cursor}")
    assert resp2.status_code == 200, resp2.text
    body2 = resp2.json()
    assert len(body2["items"]) == 2

    # Ensure no overlap with first page
    first_ids = {i["id"] for i in resp.json()["items"]}
    second_ids = {i["id"] for i in body2["items"]}
    assert first_ids.isdisjoint(second_ids)


def test_logs_404_unknown_run(runs_client):
    client, _ = runs_client
    resp = client.get(f"/api/v2/runs/{uuid4()}/logs")
    assert resp.status_code == 404

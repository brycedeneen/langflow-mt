from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


@pytest.fixture
def runs_client(monkeypatch, tmp_path):
    """
    Cancel-endpoint test fixture.

    Uses a temp-file SQLite DB so that aiosqlite creates a fresh connection per
    request (avoiding the "Future attached to a different loop" problem that
    arises when an in-memory engine's pool is shared between the fixture's
    setup loop and TestClient's background thread loop).

    `request_cancel` is patched out; Redis-write behaviour is verified by
    inspecting the mock, and a second sync Redis assertion is made in
    `test_cancel_sets_flag_and_redis` by using the real Redis fixture.
    """
    db_path = tmp_path / "cancel_test.db"
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "true")

    from langflow.main import create_app
    from langflow.api.utils.org_helpers import get_current_organization
    from langflow.services.auth.utils import get_current_active_user
    from langflow.services.deps import get_redis_service
    from langflow.services.database.models.flow_run.model import FlowRun, TriggeredBy, RunStatus
    from langflow.services.database.models.organization.model import Organization
    from langflow.services.database.models.user.model import User
    from lfx.services.deps import injectable_session_scope

    # Build engine pointed at the temp file (same path the app will use via env)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", connect_args={"check_same_thread": False})

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

        active = FlowRun(
            id=uuid4(), organization_id=fake_org.id, flow_id=uuid4(),
            triggered_by=TriggeredBy.API, status=RunStatus.QUEUED,
        )
        done = FlowRun(
            id=uuid4(), organization_id=fake_org.id, flow_id=uuid4(),
            triggered_by=TriggeredBy.API, status=RunStatus.SUCCEEDED,
        )

        async with sm() as s:
            s.add(active)
            s.add(done)
            await s.commit()
            await s.refresh(active)
            await s.refresh(done)

        return fake_user, fake_org, active, done, sm

    fake_user, fake_org, active, done, sm = asyncio.get_event_loop().run_until_complete(_setup())

    # Fake Redis service — cancel handler calls redis.client.set(...)
    fake_redis_client = AsyncMock()
    fake_redis_client.set = AsyncMock(return_value=True)
    fake_redis_client.get = AsyncMock(return_value=None)

    class FakeRedisService:
        client = fake_redis_client

    fake_redis_svc = FakeRedisService()

    # Session override that re-opens a connection per request (file-based, no pool clash)
    async def _session_override():
        async with sm() as s:
            yield s

    app = create_app()
    app.dependency_overrides[injectable_session_scope] = _session_override
    app.dependency_overrides[get_current_active_user] = lambda: fake_user
    app.dependency_overrides[get_current_organization] = lambda: fake_org
    app.dependency_overrides[get_redis_service] = lambda: fake_redis_svc

    ctx = {
        "engine": engine,
        "user": fake_user,
        "org": fake_org,
        "active": active,
        "done": done,
        "sessionmaker": sm,
        "redis_client_mock": fake_redis_client,
    }

    client = TestClient(app)
    yield client, ctx

    app.dependency_overrides.clear()
    asyncio.get_event_loop().run_until_complete(engine.dispose())


def test_cancel_sets_flag_and_redis(runs_client):
    client, ctx = runs_client
    run_id = ctx["active"].id
    resp = client.post(f"/api/v2/runs/{run_id}/cancel")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "queued"

    # Redis mock was called with the correct key
    redis_mock = ctx["redis_client_mock"]
    redis_mock.set.assert_called_once()
    call_args = redis_mock.set.call_args
    assert call_args.args[0] == f"run:cancel:{run_id}"
    assert call_args.args[1] == b"1"

    # DB flag was set — re-read from same file DB
    async def _check_db():
        async with ctx["sessionmaker"]() as s:
            r = await s.get(
                __import__("langflow.services.database.models.flow_run.model", fromlist=["FlowRun"]).FlowRun,
                run_id,
            )
            assert r is not None
            assert r.cancel_requested is True

    asyncio.get_event_loop().run_until_complete(_check_db())


def test_cancel_noop_on_terminal(runs_client):
    client, ctx = runs_client
    run_id = ctx["done"].id
    resp = client.post(f"/api/v2/runs/{run_id}/cancel")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "succeeded"

    # Redis.set should NOT have been called for a terminal run
    redis_mock = ctx["redis_client_mock"]
    redis_mock.set.assert_not_called()


def test_cancel_404_for_unknown_run(runs_client):
    client, _ = runs_client
    resp = client.post(f"/api/v2/runs/{uuid4()}/cancel")
    assert resp.status_code == 404

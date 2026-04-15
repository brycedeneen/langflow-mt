"""End-to-end smoke test: enqueue → execute → poll.

Exercises the full chain:
1. POST /api/v2/runs  → 201 + run_id
2. execute_run() called directly with a deterministic graph_runner
3. GET /api/v2/runs/{run_id} → 200 + status == "succeeded"
4. GET /api/v2/runs/{run_id}/logs → 200

Placed in tests/integration/e2e/ so the worker/conftest.py autouse
fixtures (which spin up a full ASGI app) do NOT interfere.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


# ---------------------------------------------------------------------------
# Override the parent integration conftest's autouse _start_app fixture so no
# full ASGI client is started for these tests.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _start_app():  # noqa: PT004
    """Disable the parent conftest autouse fixture that starts a full app."""
    pass


# ---------------------------------------------------------------------------
# Shared in-memory SQLite engine (file-backed so execute_run's own session
# factory sees the same rows that the TestClient committed).
# ---------------------------------------------------------------------------
@pytest.fixture
async def engine_and_factory(tmp_path):
    db_path = tmp_path / "e2e.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    @asynccontextmanager
    async def factory():
        async with sm() as s:
            yield s

    yield engine, factory
    await engine.dispose()


@pytest.fixture
async def seeded(engine_and_factory):
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.organization.model import Organization
    from langflow.services.database.models.user.model import User

    _, factory = engine_and_factory
    async with factory() as s:
        user = User(
            id=uuid4(),
            username="e2e",
            password="x",  # noqa: S106
            is_superuser=False,
            is_active=True,
        )
        org = Organization(
            id=uuid4(),
            name="e2e",
            slug="e2e",
            runs_priority_tier="default",
            runs_max_concurrent=5,
        )
        s.add_all([user, org])
        await s.commit()

        flow = Flow(
            id=uuid4(),
            name="f",
            data={},
            organization_id=org.id,
            auto_retry=False,
            max_retries=3,
            timeout_seconds=600,
        )
        s.add(flow)
        await s.commit()

        for r in (user, org, flow):
            await s.refresh(r)

    return {"user": user, "org": org, "flow": flow}


@pytest.fixture
def client_and_ctx(monkeypatch, tmp_path, engine_and_factory, seeded):
    """Build a TestClient whose session overrides point at the same SQLite DB
    used by execute_run, so both sides see the same rows."""
    monkeypatch.setenv("LANGFLOW_DISTRIBUTED_EXECUTION", "true")
    monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "true")

    from langflow.main import create_app
    from langflow.api.utils.org_helpers import get_current_organization
    from langflow.services.auth.utils import get_current_active_user
    from langflow.services.deps import get_settings_service
    from langflow.services.runs.deps import get_arq_pool
    from lfx.services.deps import injectable_session_scope

    # Flip the setting so the endpoint doesn't 503.
    get_settings_service().settings.distributed_execution = True

    engine, factory = engine_and_factory
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _session_override():
        async with sm() as s:
            yield s

    fake_arq = AsyncMock()
    fake_arq.enqueue_job = AsyncMock(return_value=None)

    async def _arq_override():
        return fake_arq

    app = create_app()
    app.dependency_overrides[injectable_session_scope] = _session_override
    app.dependency_overrides[get_current_active_user] = lambda: seeded["user"]
    app.dependency_overrides[get_current_organization] = lambda: seeded["org"]
    app.dependency_overrides[get_arq_pool] = _arq_override

    # Settings the worker function will consume.
    real_settings = get_settings_service().settings

    # Mock storage — small payloads stay inline; no real storage calls needed.
    storage = Mock()
    storage.run_payload_inline_max_bytes = 10 * 1024 * 1024

    # Worker context mirroring what WorkerSettings.on_startup populates.
    worker_ctx = {
        "redis": None,  # filled in by the test after redis_service is resolved
        "db_sessionmaker": factory,
        "storage": storage,
        "settings": real_settings,
        "arq": fake_arq,
        "graph_runner": None,  # filled in by the test
    }

    client = TestClient(app)
    yield client, worker_ctx, seeded
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_full_roundtrip(client_and_ctx, redis_service):
    """Full enqueue → execute → poll chain."""
    client, worker_ctx, seeded = client_and_ctx

    # Wire in the live Redis client (from the conftest.py redis_service fixture).
    worker_ctx["redis"] = redis_service.client

    # Deterministic runner — avoids real Graph construction.
    async def deterministic_runner(flow, triggered_by, inputs, actor_id):
        await asyncio.sleep(0)  # yield to event loop
        return {"ok": True, "echo": inputs}

    worker_ctx["graph_runner"] = deterministic_runner

    # Step 1 — POST /api/v2/runs → 201
    body = {"flow_id": str(seeded["flow"].id), "inputs": {"q": "hi"}}
    resp = client.post("/api/v2/runs", json=body)
    assert resp.status_code == 201, resp.text
    resp_data = resp.json()
    run_id = resp_data["run_id"]
    assert run_id is not None

    # Step 2 — Execute via the worker function directly (same DB, same Redis).
    from langflow.worker_app.execute import execute_run

    await execute_run(worker_ctx, run_id)

    # Step 3 — GET /api/v2/runs/{run_id} → succeeded
    resp = client.get(f"/api/v2/runs/{run_id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "succeeded", f"expected succeeded, got {data['status']!r}"
    assert data["result"] is not None

    # Step 4 — GET /api/v2/runs/{run_id}/logs → 200
    resp = client.get(f"/api/v2/runs/{run_id}/logs")
    assert resp.status_code == 200, resp.text
    logs_body = resp.json()
    assert "items" in logs_body

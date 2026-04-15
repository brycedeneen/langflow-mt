"""Conftest for worker integration tests.

These tests don't use the full Langflow app — they test worker functions
in isolation with a lightweight DB + live Redis. Override the autouse
_start_app fixture from the parent integration conftest so no HTTP client
is started.
"""
from __future__ import annotations
import asyncio
import pytest
from contextlib import asynccontextmanager
from uuid import uuid4

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from unittest.mock import AsyncMock, Mock


@pytest.fixture(autouse=True)
def _start_app():
    """Override the parent integration conftest's autouse fixture.

    Worker tests don't need the full ASGI app running.
    """
    pass


@pytest.fixture
async def engine_and_factory(tmp_path):
    db_path = tmp_path / "test_execute_run.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
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
    from langflow.services.database.models.organization.model import Organization
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.flow_run.model import FlowRun, TriggeredBy, RunStatus

    _, factory = engine_and_factory
    async with factory() as s:
        org = Organization(
            id=uuid4(),
            name="o",
            slug="o",
            runs_priority_tier="default",
            runs_max_concurrent=5,
        )
        s.add(org)
        await s.commit()

        flow = Flow(
            id=uuid4(),
            name="f",
            data={"nodes": [], "edges": []},
            organization_id=org.id,
            auto_retry=False,
            max_retries=3,
            timeout_seconds=600,
        )
        s.add(flow)
        await s.commit()

        run = FlowRun(
            id=uuid4(),
            organization_id=org.id,
            flow_id=flow.id,
            triggered_by=TriggeredBy.API,
            status=RunStatus.QUEUED,
            timeout_seconds=30,
        )
        s.add(run)
        await s.commit()

        for r in (org, flow, run):
            await s.refresh(r)

    return {"org": org, "flow": flow, "run": run}


@pytest.fixture
def mock_storage():
    """Mock storage that always inlines (returns payload, None ref)."""
    import json
    storage = Mock()
    storage.run_payload_inline_max_bytes = 10 * 1024 * 1024

    async def fake_store(run_id, kind, payload):
        data = json.dumps(payload).encode("utf-8")
        if len(data) <= 10 * 1024 * 1024:
            return payload, None
        return None, f"ref:{run_id}/{kind}.json"

    storage.save_file = AsyncMock(return_value=None)
    storage.build_full_path = Mock(return_value="fake/path")
    storage.parse_file_path = Mock(return_value=("fake", "path"))
    return storage


@pytest.fixture
def worker_ctx(engine_and_factory, redis_service, mock_storage):
    from langflow.services.runs.payload import PayloadOffloader

    _, factory = engine_and_factory

    # Build a minimal settings-like object with the attributes execute_run needs
    settings = Mock()
    settings.run_payload_inline_max_bytes = 10 * 1024 * 1024
    settings.arq_high_queue = "runs:high"
    settings.arq_default_queue = "runs:default"
    settings.arq_low_queue = "runs:low"
    settings.arq_webhooks_queue = "webhooks"

    arq = AsyncMock()
    arq.enqueue_job = AsyncMock(return_value=None)

    async def deterministic_runner(flow_data, flow_id, inputs):
        await asyncio.sleep(0.05)
        return {"ok": True, "echo": inputs}

    return {
        "redis": redis_service.client,
        "db_sessionmaker": factory,
        "storage": mock_storage,
        "settings": settings,
        "arq": arq,
        "graph_runner": deterministic_runner,
    }

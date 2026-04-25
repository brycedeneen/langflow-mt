from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from taskiq import InMemoryBroker


class _RecordingBroker(InMemoryBroker):
    """InMemoryBroker subclass that records kicks instead of executing them.

    Mirrors the pattern used in tests/unit/services/runs/test_enqueue.py so
    enqueue assertions can be made without dispatching the task.
    """

    def __init__(self) -> None:
        super().__init__()
        self.kicked = []

    async def kick(self, message) -> None:  # type: ignore[override]
        self.kicked.append(message)

    def messages_count(self) -> int:
        return len(self.kicked)


@pytest.fixture
def runs_client(monkeypatch, tmp_path):
    """Create a test client with auth/org dependencies overridden + InMemoryBroker registry."""
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("LANGFLOW_SUPERUSER", "admin")
    monkeypatch.setenv("LANGFLOW_SUPERUSER_PASSWORD", "testpassword123")

    from langflow.main import create_app
    from langflow.api.utils.org_helpers import get_current_organization
    from langflow.services.auth.utils import get_current_active_user
    from langflow.services.database.models.user.model import User
    from langflow.services.database.models.organization.model import Organization

    app = create_app()

    fake_user = User(id=uuid4(), username="tester", is_superuser=False, is_active=True)
    fake_org = Organization(
        id=uuid4(),
        name="test",
        slug="test",
        runs_priority_tier="default",
        runs_max_concurrent=5,
    )

    # Replace the module-level TIER_TO_BROKER registry that the endpoint uses
    # with InMemoryBroker instances so no real Redis is needed.
    brokers_registry = {
        "high": _RecordingBroker(),
        "default": _RecordingBroker(),
        "low": _RecordingBroker(),
    }
    monkeypatch.setattr(
        "langflow.api.v2.runs.TIER_TO_BROKER",
        brokers_registry,
    )

    app.dependency_overrides[get_current_active_user] = lambda: fake_user
    app.dependency_overrides[get_current_organization] = lambda: fake_org

    client = TestClient(app)
    client._fake_org = fake_org
    client._fake_user = fake_user
    client._brokers = brokers_registry
    yield client
    app.dependency_overrides.clear()


def test_post_runs_returns_201(runs_client, monkeypatch):
    """Enqueue a run with distributed execution enabled — expect 201 + valid body."""
    from langflow.api.v2 import runs as runs_mod
    from langflow.services.database.models.flow_run.model import RunStatus
    from langflow.services.deps import get_settings_service

    get_settings_service().settings.distributed_execution = True

    fake_run = SimpleNamespace(
        id=uuid4(),
        status=RunStatus.QUEUED,
        queued_at=datetime.now(timezone.utc),
    )

    async def _fake_enqueue(self, **kw):
        return fake_run

    monkeypatch.setattr(runs_mod.RunEnqueuer, "enqueue", _fake_enqueue)

    body = {"flow_id": str(uuid4()), "inputs": {"q": "hi"}}
    resp = runs_client.post("/api/v2/runs", json=body)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "queued"
    assert UUID(data["run_id"]) == fake_run.id
    assert "queued_at" in data


def test_post_runs_503_when_distributed_disabled(runs_client):
    """When distributed_execution is False the endpoint must return 503."""
    from langflow.services.deps import get_settings_service

    get_settings_service().settings.distributed_execution = False

    body = {"flow_id": str(uuid4()), "inputs": {"q": "hi"}}
    resp = runs_client.post("/api/v2/runs", json=body)
    assert resp.status_code == 503, resp.text

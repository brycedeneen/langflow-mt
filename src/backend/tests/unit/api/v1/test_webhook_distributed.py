"""Tests for webhook distributed execution path (Task 27).

Covers:
- flag ON  → 202 + run_id ("queued" branch via RunEnqueuer)
- flag OFF → in-process path taken (not a 202 run_id response)
"""
from __future__ import annotations

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from fastapi.testclient import TestClient


@pytest.fixture
def webhook_client(monkeypatch, tmp_path):
    monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "true")
    from langflow.main import create_app
    app = create_app()
    yield TestClient(app), app
    app.dependency_overrides.clear()


def test_webhook_enqueues_when_distributed_on(webhook_client, monkeypatch):
    """Flag on: POST /webhook/{flow_id} must return 202 with run_id + status=queued."""
    client, app = webhook_client

    # Flip the flag in the running settings service
    from langflow.services.deps import get_settings_service
    get_settings_service().settings.distributed_execution = True

    # Build a fake FlowRead and fake FlowRun
    from types import SimpleNamespace
    flow_id = uuid4()
    org_id = uuid4()
    fake_flow_read = SimpleNamespace(
        id=flow_id,
        name="f",
        endpoint_name="f",
        data={},
    )
    # The ORM Flow returned by _session.get inside the branch
    fake_db_flow = SimpleNamespace(
        id=flow_id,
        organization_id=org_id,
        auto_retry=False,
        max_retries=0,
        timeout_seconds=None,
    )
    fake_run = SimpleNamespace(
        id=uuid4(),
        status=SimpleNamespace(value="queued"),
        queued_at=datetime.now(timezone.utc),
    )

    # Override the flow-by-endpoint dependency so we don't need a real DB
    from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
    app.dependency_overrides[get_flow_by_id_or_endpoint_name] = lambda: fake_flow_read

    # Stub out webhook user discovery
    mock_auth = MagicMock()
    mock_auth.get_webhook_user = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    monkeypatch.setattr("langflow.api.v1.endpoints.get_auth_service", lambda: mock_auth)

    # Patch get_arq_pool to avoid needing a real Redis connection
    fake_arq = MagicMock()
    fake_arq.enqueue_job = AsyncMock(return_value=None)

    async def fake_arq_pool():
        return fake_arq

    monkeypatch.setattr("langflow.services.runs.deps.get_arq_pool", fake_arq_pool)

    # Patch session_scope so there's no real DB session
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_session_scope():
        mock_session = AsyncMock()
        # _session.get(_Flow, flow.id) → fake_db_flow
        mock_session.get = AsyncMock(return_value=fake_db_flow)
        yield mock_session

    monkeypatch.setattr("langflow.api.v1.endpoints.session_scope", fake_session_scope, raising=False)
    # Also patch the import path used inside the if-block (lazy import)
    import langflow.services.deps as _deps_mod
    monkeypatch.setattr(_deps_mod, "session_scope", fake_session_scope)

    # Patch RunEnqueuer.enqueue to return the fake run without touching DB
    async def fake_enqueue(self, **kw):
        return fake_run

    monkeypatch.setattr("langflow.services.runs.enqueue.RunEnqueuer.enqueue", fake_enqueue)

    # Per-flow API key validation runs before the distributed branch. This test
    # focuses on the enqueue path, so stub the validator. Dedicated auth
    # coverage lives in tests/services/database/models/flow/test_webhook_auth.py.
    async def fake_validate(org_id, flow_id, provided_key):  # noqa: ARG001
        return None

    monkeypatch.setattr("langflow.api.v1.endpoints._validate_webhook_api_key", fake_validate)

    try:
        resp = client.post(
            f"/api/v1/webhook/{flow_id}",
            json={"hello": "world"},
            headers={"x-api-key": "ADP-APICPRO-stub"},
        )
        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert "run_id" in body, f"Expected run_id in response, got: {body}"
        assert body["status"] == "queued", f"Expected status=queued, got: {body}"
    finally:
        # Always reset flag so we don't pollute other tests
        get_settings_service().settings.distributed_execution = False


def test_webhook_falls_through_when_distributed_off(webhook_client, monkeypatch):
    """Flag off: existing in-process path is taken; we must NOT get a 202 with run_id.

    The legacy path requires a running DB + auth service. We stub auth and send an
    empty body so the handler hits the "Request body is empty" 400 guard — which is
    inside the legacy path, not the distributed path — proving the flag correctly
    routes to the old code.
    """
    client, app = webhook_client

    from langflow.services.deps import get_settings_service
    get_settings_service().settings.distributed_execution = False

    from types import SimpleNamespace
    from langflow.helpers.flow import get_flow_by_id_or_endpoint_name

    fake_flow = SimpleNamespace(
        id=uuid4(),
        name="f",
        endpoint_name="f",
        organization_id=uuid4(),
        data={},
        webhook_url=None,
        webhook_secret=None,
    )
    app.dependency_overrides[get_flow_by_id_or_endpoint_name] = lambda: fake_flow

    # Stub auth service so get_webhook_user doesn't raise NotImplementedError
    mock_auth = MagicMock()
    mock_auth.get_webhook_user = AsyncMock(return_value=None)
    monkeypatch.setattr("langflow.api.v1.endpoints.get_auth_service", lambda: mock_auth)

    # Send empty body — the legacy path raises 400 "Request body is empty" before
    # doing any real work, proving we took the legacy branch (not the 202 distributed path).
    resp = client.post(f"/api/v1/webhook/{fake_flow.id}", content=b"")

    # Either 400 (empty body) or other non-202 is acceptable.
    # The key invariant: flag OFF must never produce a 202 with run_id.
    if resp.status_code == 202:
        assert "run_id" not in resp.json(), (
            "Flag was OFF but the distributed enqueue path was taken (got 202 with run_id)!"
        )
    else:
        # 400 from the "empty body" check in the legacy path is the expected outcome
        assert resp.status_code in (400, 401, 403, 422, 500), (
            f"Unexpected status {resp.status_code}: {resp.text}"
        )

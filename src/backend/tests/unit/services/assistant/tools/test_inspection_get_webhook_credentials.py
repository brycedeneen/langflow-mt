"""Tests for FlowInspectionTools.get_webhook_credentials."""

from __future__ import annotations

from uuid import uuid4

import pytest

from langflow.services.assistant.tools.inspection import FlowInspectionTools


@pytest.mark.asyncio
async def test_get_webhook_credentials_returns_endpoint_and_api_key(monkeypatch):
    org_id = uuid4()
    flow_id = uuid4()
    fake_store_data = {f"{org_id}/webhooks/{flow_id}": {"api_key": "lf_secret_xyz"}}

    class FakeStore:
        async def get(self, key):
            return fake_store_data.get(key)

    monkeypatch.setattr(
        "langflow.services.assistant.tools.inspection.get_secret_store",
        lambda: FakeStore(),
    )

    tools = FlowInspectionTools(
        {"nodes": [], "edges": []},
        flow_id=flow_id,
        org_id=org_id,
        base_url="https://example.com",
    )
    result = await tools.get_webhook_credentials()
    assert result == {
        "endpoint": f"https://example.com/api/v1/webhook/{flow_id}",
        "api_key": "lf_secret_xyz",
    }


@pytest.mark.asyncio
async def test_get_webhook_credentials_returns_error_when_no_key_provisioned(monkeypatch):
    class FakeStore:
        async def get(self, key):
            return None

    monkeypatch.setattr(
        "langflow.services.assistant.tools.inspection.get_secret_store",
        lambda: FakeStore(),
    )

    tools = FlowInspectionTools(
        {"nodes": [], "edges": []},
        flow_id=uuid4(),
        org_id=uuid4(),
        base_url="https://example.com",
    )
    result = await tools.get_webhook_credentials()
    assert result == {
        "error": (
            "no webhook api_key provisioned for this flow yet — make "
            "sure an ADP Trigger or Webhook component is in the flow "
            "and the change has been persisted"
        ),
    }


@pytest.mark.asyncio
async def test_get_webhook_credentials_returns_error_when_entry_missing_api_key(monkeypatch):
    class FakeStore:
        async def get(self, key):
            return {"created_at": "2026-04-19T00:00:00Z"}  # no api_key

    monkeypatch.setattr(
        "langflow.services.assistant.tools.inspection.get_secret_store",
        lambda: FakeStore(),
    )

    tools = FlowInspectionTools(
        {"nodes": [], "edges": []},
        flow_id=uuid4(),
        org_id=uuid4(),
        base_url="https://example.com",
    )
    result = await tools.get_webhook_credentials()
    assert "error" in result


@pytest.mark.asyncio
async def test_get_webhook_credentials_returns_error_when_context_missing():
    tools = FlowInspectionTools(
        {"nodes": [], "edges": []},
        # no flow_id / org_id / base_url
    )
    result = await tools.get_webhook_credentials()
    assert result == {"error": "webhook credentials unavailable: missing flow context"}


@pytest.mark.asyncio
async def test_get_webhook_credentials_normalizes_base_url_trailing_slash(monkeypatch):
    """Base URL with a trailing slash should not double-slash the path."""
    org_id = uuid4()
    flow_id = uuid4()
    fake_store_data = {f"{org_id}/webhooks/{flow_id}": {"api_key": "key"}}

    class FakeStore:
        async def get(self, key):
            return fake_store_data.get(key)

    monkeypatch.setattr(
        "langflow.services.assistant.tools.inspection.get_secret_store",
        lambda: FakeStore(),
    )

    tools = FlowInspectionTools(
        {"nodes": [], "edges": []},
        flow_id=flow_id,
        org_id=org_id,
        base_url="https://example.com/",
    )
    result = await tools.get_webhook_credentials()
    assert result["endpoint"] == f"https://example.com/api/v1/webhook/{flow_id}"

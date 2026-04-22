"""Integration tests for POST /api/v1/assistant/components/messages."""

from __future__ import annotations

# ruff: noqa: ARG001, ARG002  -- fixtures and ProviderClient interface stubs
# take positional args we don't use inside the test bodies.
from typing import TYPE_CHECKING, Any

import pytest
from langflow.services.assistant.providers.base import ProviderClient, StreamEvent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _ScriptedProvider(ProviderClient):
    """Replays a fixed list of ``StreamEvent`` objects on each call."""

    def __init__(self, events: list[StreamEvent]) -> None:
        self._events = events

    async def stream_with_tools(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[StreamEvent]:
        for event in self._events:
            yield event

    async def stream_with_tool_results(self, *args, **kwargs) -> AsyncIterator[StreamEvent]:
        if False:  # pragma: no cover — async generator hint
            yield
        return


def _fake_settings_factory():
    async def _fake_settings(*_args, **_kwargs):
        return {"provider": "anthropic", "model": "claude-sonnet-4-20250514", "api_key": "test-key"}

    return _fake_settings


def _minimal_body(flow_id: str, component_type: str = "FooComponent") -> dict[str, Any]:
    return {
        "flow_id": flow_id,
        "node_id": "n1",
        "node_snapshot": {
            "node_id": "n1",
            "type": component_type,
            "display_name": "Foo",
            "description": None,
            "template": {"x": {"display_name": "X", "value": 0}},
            "outputs": [],
        },
        "neighbor_snapshots": [],
        "thread": [],
        "user_message": "hi",
    }


async def _create_flow(client: AsyncClient, headers: dict[str, str]) -> str:
    resp = await client.post(
        "/api/v1/flows/",
        headers=headers,
        json={"name": "Component Assist test flow", "data": {"nodes": [], "edges": []}},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_streams_token_and_done(
    client: AsyncClient, logged_in_headers, active_super_user, monkeypatch
):
    """Scripted provider → SSE stream carries token + done events.

    Verifies the end-to-end wiring: endpoint → service → LLM adapter → scripted
    provider → SSE serializer.
    """
    from langflow.api.v1 import component_assist as component_assist_module

    monkeypatch.setattr(
        component_assist_module,
        "_create_provider_client",
        lambda *_a, **_kw: _ScriptedProvider([StreamEvent(type="token", text="hello")]),
        raising=True,
    )
    monkeypatch.setattr(
        component_assist_module,
        "_load_assistant_settings",
        _fake_settings_factory(),
        raising=True,
    )

    flow_id = await _create_flow(client, logged_in_headers)
    body = _minimal_body(flow_id)

    response = await client.post(
        "/api/v1/assistant/components/messages",
        headers=logged_in_headers,
        json=body,
        timeout=30,
    )
    assert response.status_code == 200, response.text
    text = response.text
    assert '"type": "token"' in text
    assert '"text": "hello"' in text
    assert '"type": "done"' in text


@pytest.mark.asyncio
async def test_404_when_flow_missing(
    client: AsyncClient, logged_in_headers, active_super_user, monkeypatch
):
    """A missing flow returns 404 before any streaming happens."""
    from langflow.api.v1 import component_assist as component_assist_module

    # Settings need to be valid so the handler reaches the flow check.
    monkeypatch.setattr(
        component_assist_module,
        "_load_assistant_settings",
        _fake_settings_factory(),
        raising=True,
    )

    body = _minimal_body("00000000-0000-0000-0000-000000000000")
    resp = await client.post(
        "/api/v1/assistant/components/messages", headers=logged_in_headers, json=body
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_400_when_component_opts_out(
    client: AsyncClient, logged_in_headers, active_super_user, monkeypatch
):
    """Posting for a component with ``assist_enabled=False`` returns 400."""
    from langflow.api.v1 import component_assist as component_assist_module

    class _OptedOut:
        __name__ = "OptedOutComponent"
        assist_enabled = False

    monkeypatch.setattr(
        component_assist_module,
        "_load_assistant_settings",
        _fake_settings_factory(),
        raising=True,
    )
    monkeypatch.setattr(
        component_assist_module,
        "_resolve_component_class",
        lambda name: _OptedOut if name == "OptedOutComponent" else None,
        raising=True,
    )

    flow_id = await _create_flow(client, logged_in_headers)
    body = _minimal_body(flow_id, component_type="OptedOutComponent")

    resp = await client.post(
        "/api/v1/assistant/components/messages", headers=logged_in_headers, json=body
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "opted out" in detail or "assist_enabled" in detail


@pytest.mark.asyncio
async def test_tool_call_proposal_roundtrip(
    client: AsyncClient, logged_in_headers, active_super_user, monkeypatch
):
    """End-to-end smoke: scripted provider emits a propose_config_update tool call
    whose patch targets a valid template key; the SSE stream carries exactly one
    tool_call event with the patch intact, then terminates with done."""
    from langflow.api.v1 import component_assist as component_assist_module

    events = [
        StreamEvent(
            type="tool_call",
            tool_call_id="call_1",
            tool_name="propose_config_update",
            tool_args={
                "node_id": "n1",
                "patch": {"x": 5},
                "rationale": "user asked to set x",
            },
        ),
    ]
    monkeypatch.setattr(
        component_assist_module,
        "_create_provider_client",
        lambda *_a, **_kw: _ScriptedProvider(events),
        raising=True,
    )
    monkeypatch.setattr(
        component_assist_module,
        "_load_assistant_settings",
        _fake_settings_factory(),
        raising=True,
    )

    flow_id = await _create_flow(client, logged_in_headers)
    body = _minimal_body(flow_id)  # node_snapshot.template has key "x"
    body["user_message"] = "set x to 5"

    response = await client.post(
        "/api/v1/assistant/components/messages",
        headers=logged_in_headers,
        json=body,
        timeout=30,
    )
    assert response.status_code == 200, response.text
    text = response.text

    # Exactly one tool_call event for propose_config_update.
    tool_call_lines = [
        line for line in text.splitlines() if '"type": "tool_call"' in line
    ]
    assert len(tool_call_lines) == 1, f"expected 1 tool_call event, got {tool_call_lines}"
    assert '"name": "propose_config_update"' in tool_call_lines[0]
    assert '"patch": {"x": 5}' in tool_call_lines[0]
    assert '"rationale": "user asked to set x"' in tool_call_lines[0]

    # Stream terminates with done.
    assert '"type": "done"' in text


@pytest.mark.asyncio
async def test_400_when_settings_unconfigured(
    client: AsyncClient, logged_in_headers, active_super_user, monkeypatch
):
    """If the org has no assistant provider/model/api_key, the endpoint returns 400."""
    from langflow.api.v1 import component_assist as component_assist_module

    async def _unset_settings(*_args, **_kwargs):
        return {"provider": None, "model": None, "api_key": None}

    monkeypatch.setattr(
        component_assist_module, "_load_assistant_settings", _unset_settings, raising=True
    )

    flow_id = await _create_flow(client, logged_in_headers)
    body = _minimal_body(flow_id)
    resp = await client.post(
        "/api/v1/assistant/components/messages", headers=logged_in_headers, json=body
    )
    assert resp.status_code == 400
    assert "settings not configured" in resp.json()["detail"].lower()

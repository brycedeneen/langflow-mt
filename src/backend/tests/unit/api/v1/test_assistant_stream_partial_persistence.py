"""Regression test: if the assistant's SSE stream errors mid-way, any flow
mutations that already succeeded (nodes added, edges connected) must still be
persisted to the DB.

Root cause: pre-fix, persistence scheduling lived inside the try-block of the
event_generator in src/backend/base/langflow/api/v1/assistant.py, so any
exception (rate-limit, network drop, provider timeout) caused the scheduler to
be skipped and in-memory mutations to be lost. The fix moves scheduling to a
finally block.
"""

from __future__ import annotations

from typing import Any, AsyncIterator
from uuid import UUID

import pytest
from sqlmodel import select

from langflow.services.assistant.providers.base import (
    ProviderClient,
    StreamEvent,
    ToolResult,
)
from langflow.services.database.models import Flow
from langflow.services.deps import session_scope


class _PartialThenRaiseProvider(ProviderClient):
    """Emits two add_component tool calls + one connect_edge tool call,
    then raises an exception simulating a rate-limit hit.
    """

    def __init__(self) -> None:
        self._first_turn_done = False

    async def stream_with_tools(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[StreamEvent]:
        # First turn: emit two tool_calls, then END the generator (no
        # message_complete). This is how a real provider signals "I want
        # tool results" — send_message will execute the tools and then
        # call stream_with_tool_results for the next turn.
        yield StreamEvent(
            type="tool_call",
            tool_call_id="call_1",
            tool_name="add_component",
            tool_args={"component_type": "Webhook", "position": "auto"},
        )
        yield StreamEvent(
            type="tool_call",
            tool_call_id="call_2",
            tool_name="add_component",
            tool_args={"component_type": "Slack", "position": "auto"},
        )
        # No message_complete — service will run the tools and loop.

    async def stream_with_tool_results(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
        tool_results: list[ToolResult],
    ) -> AsyncIterator[StreamEvent]:
        # Second turn: simulate a rate-limit error BEFORE any tool call or
        # message_complete. At this point the service has already executed
        # the first turn's two add_component tools and populated
        # service.mutation_tools.flow_data["nodes"] with 2 entries. We need
        # persistence to capture that state despite the error.
        if False:
            yield  # pragma: no cover — make this an async generator
        raise RuntimeError("Rate limit exceeded (429)")


@pytest.mark.asyncio
async def test_stream_error_still_persists_partial_flow_mutations(
    client, logged_in_headers, active_super_user, monkeypatch
):
    """Exercise the endpoint end-to-end: stream errors mid-way, DB still shows
    the nodes that were added before the error.
    """
    # 1. Create a blank flow via the REST API so organization_id is set
    # correctly for the test user/org (direct-DB insert skips that wiring).
    create_resp = await client.post(
        "/api/v1/flows/",
        headers=logged_in_headers,
        json={
            "name": "Partial-persist regression",
            "data": {"nodes": [], "edges": []},
        },
    )
    assert create_resp.status_code in (200, 201), create_resp.text
    flow_id = create_resp.json()["id"]

    # 2. Patch the provider factory so the endpoint uses our partial/raising client
    from langflow.api.v1 import assistant as assistant_module

    def _fake_create_provider_client(provider, model, api_key):
        return _PartialThenRaiseProvider()

    monkeypatch.setattr(
        assistant_module,
        "_create_provider_client",
        _fake_create_provider_client,
        raising=True,
    )

    # 3. Ensure settings are configured for this test user/org
    async def _fake_settings(*args, **kwargs):
        return {"provider": "anthropic", "model": "claude-sonnet-4-20250514", "api_key": "test-key"}

    monkeypatch.setattr(
        assistant_module,
        "_load_assistant_settings",
        _fake_settings,
        raising=False,
    )

    # 4. Hit the streaming endpoint. sse_starlette returns a 200 regardless of
    # stream errors — the error is emitted as an SSE event and logged.
    response = await client.post(
        f"/api/v1/assistant/flows/{flow_id}/messages",
        headers=logged_in_headers,
        json={"content": "build me a slack notifier"},
        timeout=30,
    )
    assert response.status_code == 200

    # Wait for background persistence task to drain
    import asyncio
    for _ in range(20):
        await asyncio.sleep(0.1)
        async with session_scope() as session:
            refreshed = (
                await session.exec(select(Flow).where(Flow.id == UUID(flow_id)))
            ).one_or_none()
            if refreshed and refreshed.data and len(refreshed.data.get("nodes", [])) >= 2:
                break

    # 5. Assert partial mutations DID persist despite the mid-stream error
    async with session_scope() as session:
        refreshed = (
            await session.exec(select(Flow).where(Flow.id == UUID(flow_id)))
        ).one()
    nodes = refreshed.data.get("nodes", []) if refreshed.data else []
    # The first two add_component calls happened before the error → should persist
    assert len(nodes) >= 2, (
        f"Expected partial mutations (>=2 nodes) to persist after mid-stream error, "
        f"got {len(nodes)} nodes: {[n.get('id') for n in nodes]}"
    )

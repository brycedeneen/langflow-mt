"""Integration tests for POST /api/v1/assistant/flows/{flow_id}/greet."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlmodel import select
from unittest.mock import AsyncMock, patch

from langflow.services.database.models.assistant.model import (
    AssistantConversation,
    AssistantMessage,
)
from langflow.services.deps import session_scope


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_flow_via_api(client: AsyncClient, headers: dict, name: str = "Test Flow") -> str:
    """Create a flow via the REST API so that organization_id is set correctly."""
    resp = await client.post(
        "/api/v1/flows/",
        headers=headers,
        json={"name": name, "data": {"nodes": [], "edges": []}},
    )
    assert resp.status_code in (200, 201), f"Flow creation failed: {resp.text}"
    return resp.json()["id"]


FAKE_SETTINGS = {
    "provider": "anthropic",
    "model": "claude-haiku-4-5-20251001",
    "api_key": "sk-ant-fake-key",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_greet_creates_first_assistant_message(
    client: AsyncClient, logged_in_headers
):
    flow_id = await _create_flow_via_api(client, logged_in_headers, name="Greet me")

    from langflow.api.v1 import assistant as assistant_module

    async def _fake_settings(*args, **kwargs):
        return FAKE_SETTINGS

    with patch.object(assistant_module, "_load_assistant_settings", side_effect=_fake_settings), \
         patch(
             "langflow.services.assistant.service.AssistantService.generate_once",
             new_callable=AsyncMock,
             return_value="Hello! How can I help you build your flow today?",
         ):
        response = await client.post(
            f"/api/v1/assistant/flows/{flow_id}/greet",
            headers=logged_in_headers,
        )

    assert response.status_code in (200, 201), response.text
    body = response.json()
    assert body["role"] == "assistant"
    assert body["content"], "greeting content must not be empty"

    from uuid import UUID

    async with session_scope() as session:
        convo = (
            await session.exec(
                select(AssistantConversation).where(
                    AssistantConversation.flow_id == UUID(flow_id)
                )
            )
        ).one()
        msgs = (
            await session.exec(
                select(AssistantMessage).where(
                    AssistantMessage.conversation_id == convo.id
                )
            )
        ).all()
        assert len(msgs) == 1
        assert msgs[0].role == "assistant"


@pytest.mark.asyncio
async def test_greet_is_idempotent_returns_409_if_already_greeted(
    client: AsyncClient, logged_in_headers
):
    flow_id = await _create_flow_via_api(client, logged_in_headers, name="Greeted")

    from langflow.api.v1 import assistant as assistant_module

    async def _fake_settings(*args, **kwargs):
        return FAKE_SETTINGS

    with patch.object(assistant_module, "_load_assistant_settings", side_effect=_fake_settings), \
         patch(
             "langflow.services.assistant.service.AssistantService.generate_once",
             new_callable=AsyncMock,
             return_value="Welcome back!",
         ):
        first = await client.post(
            f"/api/v1/assistant/flows/{flow_id}/greet",
            headers=logged_in_headers,
        )
        assert first.status_code in (200, 201), first.text

        second = await client.post(
            f"/api/v1/assistant/flows/{flow_id}/greet",
            headers=logged_in_headers,
        )
        assert second.status_code == 409, second.text


@pytest.mark.asyncio
async def test_greet_returns_400_when_settings_missing(
    client: AsyncClient, logged_in_headers
):
    flow_id = await _create_flow_via_api(client, logged_in_headers, name="Unconfigured")

    from langflow.api.v1 import assistant as assistant_module

    async def _fake_no_settings(*args, **kwargs):
        return {"provider": None, "model": None, "api_key": None}

    with patch.object(assistant_module, "_load_assistant_settings", side_effect=_fake_no_settings):
        response = await client.post(
            f"/api/v1/assistant/flows/{flow_id}/greet",
            headers=logged_in_headers,
        )

    assert response.status_code == 400

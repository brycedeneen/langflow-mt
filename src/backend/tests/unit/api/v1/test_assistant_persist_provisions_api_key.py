"""Regression test: when the assistant's persist path writes a flow whose
``data`` contains a webhook-like node (Webhook or ADP Trigger), it must also
provision a per-flow webhook API key in the secret store.

Pre-fix, ``_persist_assistant_turn`` only wrote ``db_flow.data = final_flow_data``
without invoking ``_provision_webhook_api_key``. Result: when the assistant
added an ADP Trigger via mutation tools, no api_key landed in the secret store
and downstream tools (e.g. ``get_webhook_credentials``) had nothing to read.

The fix mirrors what ``update_flow`` in ``api/v1/flows.py`` does after writing
``db_flow.data``.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient

from langflow.services.deps import session_scope


@pytest.fixture
def in_memory_secret_store(monkeypatch):
    """Force ``get_secret_store`` to return a fresh in-memory backend.

    The factory caches a module-level singleton, so we swap it out for an
    ``InMemorySecretStore`` and undo afterwards. Both call sites
    (``api.v1.flows`` and the assistant persist path) import the same factory
    module, so monkeypatching the singleton there covers both.
    """
    from lfx.services.secret_store import factory as secret_store_factory

    store = secret_store_factory.InMemorySecretStore()
    monkeypatch.setattr(secret_store_factory, "_instance", store, raising=False)
    return store


@pytest.mark.asyncio
async def test_persist_provisions_api_key_when_assistant_adds_adp_trigger(
    client: AsyncClient,
    logged_in_headers,
    in_memory_secret_store,
):
    """End-to-end-ish: create a webhook-less flow, then call the persist
    helper directly with flow data containing an ADP Trigger node, and assert
    that ``{org_id}/webhooks/{flow_id}`` now exists in the secret store with
    an ``api_key``.
    """
    from langflow.api.v1.assistant import _persist_assistant_turn
    from langflow.services.database.models import Flow
    from langflow.services.database.models.assistant.model import AssistantConversation
    from sqlmodel import select

    # 1. Create a flow with NO webhook so initial provisioning didn't run.
    create_resp = await client.post(
        "/api/v1/flows/",
        headers=logged_in_headers,
        json={"name": "Assist provisions key", "data": {"nodes": [], "edges": []}},
    )
    assert create_resp.status_code in (200, 201), create_resp.text
    flow_id = UUID(create_resp.json()["id"])

    # Pre-condition: secret store has no entry for this flow yet.
    # Also create a conversation row so the persist path's AssistantMessage
    # inserts satisfy their FK and the inner session_scope commits cleanly.
    async with session_scope() as session:
        flow = (await session.exec(select(Flow).where(Flow.id == flow_id))).one()
        org_id = flow.organization_id
        assert org_id is not None
        conversation = AssistantConversation(flow_id=flow_id, org_id=org_id)
        session.add(conversation)
        await session.flush()
        conversation_id = conversation.id
    assert await in_memory_secret_store.get(f"{org_id}/webhooks/{flow_id}") is None

    # 2. Build the flow data the assistant would produce after adding an ADP
    # Trigger via the add_component tool. Detection in
    # services/database/models/flow/utils.py keys off the node *id* prefix,
    # so the id must start with "ADPTrigger" (or "Webhook").
    final_flow_data = {
        "nodes": [
            {
                "id": "ADPTrigger-abc123",
                "type": "genericNode",
                "data": {
                    "type": "ADPTriggerComponent",
                    "node": {"template": {}},
                },
            }
        ],
        "edges": [],
    }

    # 3. Call the persist helper exactly the way the SSE generator does.
    # ``flow_patches`` non-empty + ``final_flow_data`` not None is what gates
    # the db_flow.data write block.
    await _persist_assistant_turn(
        conversation_id=conversation_id,
        user_id=None,
        user_content="add an ADP Trigger",
        accumulated_text="",
        tool_calls_list=[],
        tool_messages=[],
        flow_patches=[{"op": "add_node", "node_id": "ADPTrigger-abc123"}],
        flow_id=flow_id,
        final_flow_data=final_flow_data,
    )

    # 4. The secret store must now contain the per-flow webhook api_key.
    entry = await in_memory_secret_store.get(f"{org_id}/webhooks/{flow_id}")
    assert entry is not None, (
        f"Expected secret store entry at {org_id}/webhooks/{flow_id} after "
        "persist path detected an ADP Trigger, got nothing."
    )
    assert entry.get("api_key"), f"Entry exists but has no api_key: {entry}"

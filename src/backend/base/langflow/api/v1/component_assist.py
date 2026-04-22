"""SSE endpoint for the per-component ephemeral ADP Assist.

Exposes ``POST /api/v1/assistant/components/messages``. Scoped to configuring a
single node. Stateless: the request carries the full thread plus node + neighbor
snapshots; nothing is persisted between turns. Components can opt out via
``assist_enabled: ClassVar[bool] = False`` on their class (enforced here with
a 400 response).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.utils.core import CurrentOrg
from langflow.api.v1.assistant import (
    _create_provider_client,
    _get_flow_with_org_check,
    _load_assistant_settings,
)
from langflow.services.component_assist.guide_registry import (
    is_assist_enabled,
)
from langflow.services.component_assist.guide_registry import (
    resolve as resolve_guide,
)
from langflow.services.component_assist.schemas import ComponentAssistRequest
from langflow.services.component_assist.service import ComponentAssistService

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langflow.services.assistant.providers.base import ProviderClient


router = APIRouter(prefix="/assistant/components", tags=["Assistant"])


def _resolve_component_class(type_name: str) -> type | None:
    """Look up the Component subclass by its class name via the loader registry.

    Returns ``None`` if the name doesn't map to a known component — callers
    fall back to the generic prompt and skip the opt-out check.
    """
    try:
        from langflow.interface.types import get_all_components
    except ImportError:
        return None
    try:
        registry = get_all_components()
    except Exception:  # noqa: BLE001 — registry lookup failure must not 500 the request
        return None
    for component_cls in registry.values():
        if getattr(component_cls, "__name__", None) == type_name:
            return component_cls
    return None


class _ProviderLLMAdapter:
    """Bridge the existing ``ProviderClient`` to ``ComponentAssistService.LLMClient``.

    ``ProviderClient.stream_with_tools`` yields ``StreamEvent`` dataclasses;
    ``ComponentAssistService`` consumes dicts with event types it understands.
    This adapter translates.
    """

    def __init__(self, provider: ProviderClient) -> None:
        self._provider = provider

    async def stream(
        self,
        *,
        system_prompt: str,
        thread: list[dict[str, Any]],
        user_message: str,
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {"role": m.get("role"), "content": m.get("content", "")} for m in thread
        ]
        messages.append({"role": "user", "content": user_message})

        async def _gen() -> AsyncIterator[dict[str, Any]]:
            async for event in self._provider.stream_with_tools(messages, system_prompt, tools):
                if event.type == "token":
                    yield {"type": "token", "text": event.text or ""}
                elif event.type == "tool_call":
                    yield {
                        "type": "tool_call",
                        "name": event.tool_name,
                        "args": event.tool_args or {},
                    }
                elif event.type == "error":
                    yield {"type": "error", "error": event.error_message or "LLM error"}
                # message_complete / tool_result_request are intentionally ignored —
                # ComponentAssistService terminates on its own when the turn's stream ends.

        return _gen()


@router.post("/messages")
async def component_assist_messages(
    body: ComponentAssistRequest,
    current_user: CurrentActiveUser,
    org: CurrentOrg,
    session: DbSession,
):
    """Stream the assistant's reply as SSE events.

    Events emitted (one JSON object per ``data:`` line):
      - ``{"type":"token","text":"..."}`` — text delta
      - ``{"type":"tool_call","name":"propose_config_update","args":{...}}`` — proposal
      - ``{"type":"done"}`` — stream complete
      - ``{"type":"error","error":"..."}`` — terminating error
    """
    # Auth: same flow-scope check the flow-level assistant uses.
    await _get_flow_with_org_check(session, body.flow_id, org.id)

    # Opt-out: components with their own bespoke assistant return 400.
    component_cls = _resolve_component_class(body.node_snapshot.type)
    if component_cls is not None and not is_assist_enabled(component_cls):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Component '{body.node_snapshot.type}' has opted out of ADP Assist "
                "(assist_enabled=False). It ships with its own bespoke agent."
            ),
        )
    guide = resolve_guide(component_cls) if component_cls is not None else None

    # Same provider settings as the flow-level assistant — inherited, no new config surface.
    settings = await _load_assistant_settings(session, org.id, current_user.id)
    if not all(settings.get(k) for k in ("provider", "model", "api_key")):
        raise HTTPException(
            status_code=400,
            detail="Assistant settings not configured. Set provider, model, and API key first.",
        )
    provider = _create_provider_client(
        settings["provider"], settings["model"], settings["api_key"]
    )
    llm = _ProviderLLMAdapter(provider)

    service = ComponentAssistService(llm=llm, guide=guide)

    async def event_gen() -> AsyncIterator[dict[str, str]]:
        async for event in service.stream_reply(body):
            yield {"event": "message", "data": json.dumps(event)}

    return EventSourceResponse(event_gen())

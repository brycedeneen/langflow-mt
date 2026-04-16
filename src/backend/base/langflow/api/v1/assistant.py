"""REST + SSE API endpoints for the flow builder assistant."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import asyncio

from fastapi import APIRouter, HTTPException
from lfx.log import logger
from pydantic import BaseModel
from sqlmodel import select
from sse_starlette.sse import EventSourceResponse

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.utils.core import CurrentOrg
from langflow.services.assistant.providers.anthropic_provider import AnthropicProviderClient
from langflow.services.assistant.providers.openai_provider import OpenAIProviderClient
from langflow.services.assistant.service import AssistantService
from langflow.services.database.models.assistant.model import AssistantConversation, AssistantMessage
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.variable.model import Variable

router = APIRouter(prefix="/assistant", tags=["Assistant"])

# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class SendMessageRequest(BaseModel):
    content: str


class AssistantSettingsRequest(BaseModel):
    provider: str
    model: str
    api_key: str | None = None


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str | None = None
    tool_calls: Any | None = None
    tool_call_id: str | None = None
    tool_result: Any | None = None
    created_at: str | None = None


class ConversationResponse(BaseModel):
    conversation_id: str | None = None
    messages: list[MessageResponse]
    settings_configured: bool


class SettingsResponse(BaseModel):
    provider: str | None = None
    model: str | None = None
    has_key: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ASSISTANT_VAR_NAMES = ("assistant.provider", "assistant.model", "assistant.api_key")


async def _get_flow_with_org_check(
    session, flow_id: UUID, org_id: UUID
) -> Flow:
    """Load a flow and verify it belongs to the given org."""
    flow = await session.get(Flow, flow_id)
    if flow is None:
        raise HTTPException(status_code=404, detail="Flow not found")
    if flow.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Flow does not belong to your organization")
    return flow


async def _load_assistant_settings(session, org_id: UUID, user_id: UUID) -> dict[str, str | None]:
    """Load assistant.* variables for the org."""
    stmt = select(Variable).where(
        Variable.organization_id == org_id,
        Variable.name.in_(ASSISTANT_VAR_NAMES),  # type: ignore[union-attr]
    )
    rows = (await session.exec(stmt)).all()
    settings: dict[str, str | None] = {"provider": None, "model": None, "api_key": None}
    for row in rows:
        key = row.name.replace("assistant.", "")
        settings[key] = row.value
    return settings


async def _upsert_variable(
    session, org_id: UUID, user_id: UUID, name: str, value: str
) -> None:
    """Create or update a Variable scoped to an org."""
    stmt = select(Variable).where(
        Variable.organization_id == org_id,
        Variable.name == name,
    )
    existing = (await session.exec(stmt)).first()
    if existing is not None:
        existing.value = value
        session.add(existing)
    else:
        var = Variable(
            name=name,
            value=value,
            type="assistant_setting",
            default_fields=[],
            user_id=user_id,
            organization_id=org_id,
        )
        session.add(var)


def _create_provider_client(provider: str, model: str, api_key: str):
    """Instantiate the correct provider client."""
    if provider == "openai":
        return OpenAIProviderClient(api_key=api_key, model=model)
    elif provider == "anthropic":
        return AnthropicProviderClient(api_key=api_key, model=model)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")


def _db_message_to_dict(msg: AssistantMessage) -> dict[str, Any]:
    """Convert a DB message to the dict format expected by AssistantService."""
    d: dict[str, Any] = {"role": msg.role}
    if msg.content is not None:
        d["content"] = msg.content
    if msg.tool_calls is not None:
        d["tool_calls"] = msg.tool_calls
    if msg.tool_call_id is not None:
        d["tool_call_id"] = msg.tool_call_id
        # tool role messages need content as the result
        if msg.tool_result is not None:
            d["content"] = json.dumps(msg.tool_result) if not isinstance(msg.tool_result, str) else msg.tool_result
    return d


# ---------------------------------------------------------------------------
# GET /flows/{flow_id}/conversation
# ---------------------------------------------------------------------------


@router.get("/flows/{flow_id}/conversation")
async def get_conversation(
    flow_id: UUID,
    current_user: CurrentActiveUser,
    org: CurrentOrg,
    session: DbSession,
) -> ConversationResponse:
    """Load (or acknowledge absence of) a conversation for a flow."""
    await _get_flow_with_org_check(session, flow_id, org.id)

    # Check if assistant settings exist
    settings = await _load_assistant_settings(session, org.id, current_user.id)
    settings_configured = bool(settings.get("provider") and settings.get("model") and settings.get("api_key"))

    # Load conversation
    stmt = select(AssistantConversation).where(AssistantConversation.flow_id == flow_id)
    conversation = (await session.exec(stmt)).first()

    if conversation is None:
        return ConversationResponse(
            conversation_id=None,
            messages=[],
            settings_configured=settings_configured,
        )

    msg_stmt = (
        select(AssistantMessage)
        .where(AssistantMessage.conversation_id == conversation.id)
        .order_by(AssistantMessage.created_at)
    )
    msg_rows = (await session.exec(msg_stmt)).all()
    messages = [
        MessageResponse(
            id=str(m.id),
            role=m.role,
            content=m.content,
            tool_calls=m.tool_calls,
            tool_call_id=m.tool_call_id,
            tool_result=m.tool_result,
            created_at=m.created_at.isoformat() if m.created_at else None,
        )
        for m in msg_rows
    ]

    return ConversationResponse(
        conversation_id=str(conversation.id),
        messages=messages,
        settings_configured=settings_configured,
    )


# ---------------------------------------------------------------------------
# Background persistence (runs outside SSE generator context)
# ---------------------------------------------------------------------------


async def _persist_assistant_turn(
    *,
    conversation_id,
    user_id,
    user_content: str,
    accumulated_text: str,
    tool_calls_list: list,
    tool_messages: list,
    flow_patches: list,
    flow_id,
    final_flow_data: dict | None,
) -> None:
    """Persist the assistant turn to the database.

    Runs as a background asyncio task so it has access to the normal
    event-loop greenlet context that SQLAlchemy's async sessions require
    (which is not available inside sse_starlette's generator).
    """
    from langflow.services.deps import session_scope

    try:
        async with session_scope() as db:
            user_msg = AssistantMessage(
                conversation_id=conversation_id,
                user_id=user_id,
                role="user",
                content=user_content,
            )
            db.add(user_msg)

            assistant_msg = AssistantMessage(
                conversation_id=conversation_id,
                user_id=None,
                role="assistant",
                content=accumulated_text or None,
                tool_calls=tool_calls_list if tool_calls_list else None,
            )
            db.add(assistant_msg)

            for tm in tool_messages:
                tool_msg = AssistantMessage(
                    conversation_id=conversation_id,
                    user_id=None,
                    role="tool",
                    tool_call_id=tm["tool_call_id"],
                    content=json.dumps(tm["result"]) if tm["result"] else None,
                    tool_result=tm["result"],
                )
                db.add(tool_msg)

            if flow_patches and final_flow_data is not None:
                db_flow = await db.get(Flow, flow_id)
                if db_flow is not None:
                    db_flow.data = final_flow_data
                    db.add(db_flow)
    except Exception:
        logger.exception("Failed to persist assistant turn for flow %s", flow_id)


# ---------------------------------------------------------------------------
# POST /flows/{flow_id}/messages  (SSE stream)
# ---------------------------------------------------------------------------


@router.post("/flows/{flow_id}/messages")
async def send_message(
    flow_id: UUID,
    body: SendMessageRequest,
    current_user: CurrentActiveUser,
    org: CurrentOrg,
    session: DbSession,
):
    """Send a message to the assistant and stream back SSE events."""
    # --- Pre-flight: load flow, settings, conversation (all within request session) ---
    flow = await _get_flow_with_org_check(session, flow_id, org.id)
    flow_data = flow.data or {}

    settings = await _load_assistant_settings(session, org.id, current_user.id)
    if not settings.get("provider") or not settings.get("model") or not settings.get("api_key"):
        raise HTTPException(status_code=400, detail="Assistant settings not configured. Set provider, model, and API key first.")

    provider_client = _create_provider_client(settings["provider"], settings["model"], settings["api_key"])

    # Load or create conversation
    stmt = select(AssistantConversation).where(AssistantConversation.flow_id == flow_id)
    conversation = (await session.exec(stmt)).first()
    if conversation is None:
        conversation = AssistantConversation(flow_id=flow_id, org_id=org.id)
        session.add(conversation)
        await session.flush()

    conversation_id = conversation.id

    # Load conversation history via explicit query (avoid relationship lazy-load greenlet issues)
    history_stmt = (
        select(AssistantMessage)
        .where(AssistantMessage.conversation_id == conversation_id)
        .order_by(AssistantMessage.created_at)
    )
    history_rows = (await session.exec(history_stmt)).all()
    history_dicts: list[dict[str, Any]] = [_db_message_to_dict(m) for m in history_rows]

    # Capture IDs we'll need in the SSE generator (avoid referencing ORM objects)
    org_id = org.id
    user_id = current_user.id
    model_name = settings["model"]
    user_content = body.content

    # Shared state between generator and persistence task
    persist_data: dict[str, Any] = {
        "accumulated_text": "",
        "tool_calls_list": [],
        "tool_messages": [],
        "flow_patches": [],
        "final_flow_data": None,
    }

    async def event_generator():
        try:
            service = AssistantService(
                provider_client=provider_client,
                flow_data=flow_data,
                flow_id=flow_id,
                org_id=org_id,
                user_id=user_id,
                model_name=model_name,
            )
            service.set_conversation_history(history_dicts)

            async for event in service.send_message(user_content):
                event_type = event.get("type", "unknown")

                if event_type == "token":
                    persist_data["accumulated_text"] += event.get("text", "")
                    yield {"event": "token", "data": json.dumps({"text": event.get("text", "")})}

                elif event_type == "tool_call":
                    persist_data["tool_calls_list"].append({
                        "id": event.get("tool_call_id"),
                        "name": event.get("tool_name"),
                        "args": event.get("tool_args"),
                    })
                    yield {"event": "tool_call", "data": json.dumps({
                        "tool_call_id": event.get("tool_call_id"),
                        "tool_name": event.get("tool_name"),
                        "tool_args": event.get("tool_args"),
                    })}

                elif event_type == "tool_result":
                    persist_data["tool_messages"].append({
                        "tool_call_id": event.get("tool_call_id"),
                        "tool_name": event.get("tool_name"),
                        "result": event.get("result"),
                    })
                    yield {"event": "tool_result", "data": json.dumps({
                        "tool_call_id": event.get("tool_call_id"),
                        "tool_name": event.get("tool_name"),
                        "result": event.get("result"),
                    })}

                elif event_type == "flow_patch":
                    patch = event.get("patch")
                    persist_data["flow_patches"].append(patch)
                    yield {"event": "flow_patch", "data": json.dumps({"patch": patch})}

                elif event_type == "message_complete":
                    yield {"event": "message_complete", "data": json.dumps({})}

                elif event_type == "error":
                    yield {"event": "error", "data": json.dumps({"error": event.get("error", "Unknown error")})}

            persist_data["final_flow_data"] = service.mutation_tools.flow_data

            # Fire-and-forget persistence in a background task.
            # session_scope requires the ASGI greenlet context which isn't
            # available inside sse_starlette's generator. We schedule it as a
            # separate asyncio task so it runs in the main event-loop context.
            asyncio.create_task(_persist_assistant_turn(
                conversation_id=conversation_id,
                user_id=user_id,
                user_content=user_content,
                accumulated_text=persist_data["accumulated_text"],
                tool_calls_list=persist_data["tool_calls_list"],
                tool_messages=persist_data["tool_messages"],
                flow_patches=persist_data["flow_patches"],
                flow_id=flow_id,
                final_flow_data=persist_data["final_flow_data"],
            ))

        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            logger.error("Assistant SSE error for flow %s: %s\n%s", flow_id, exc, tb)
            print(f"[ASSISTANT ERROR] {exc}\n{tb}", flush=True)
            yield {"event": "error", "data": json.dumps({"error": str(exc)})}

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# DELETE /flows/{flow_id}/conversation
# ---------------------------------------------------------------------------


@router.delete("/flows/{flow_id}/conversation")
async def delete_conversation(
    flow_id: UUID,
    current_user: CurrentActiveUser,
    org: CurrentOrg,
    session: DbSession,
):
    """Delete the conversation and all messages for a flow."""
    await _get_flow_with_org_check(session, flow_id, org.id)

    stmt = select(AssistantConversation).where(AssistantConversation.flow_id == flow_id)
    conversation = (await session.exec(stmt)).first()
    if conversation is None:
        return {"ok": True}

    await session.delete(conversation)
    return {"ok": True}


# ---------------------------------------------------------------------------
# GET /settings
# ---------------------------------------------------------------------------


@router.get("/settings")
async def get_settings(
    current_user: CurrentActiveUser,
    org: CurrentOrg,
    session: DbSession,
) -> SettingsResponse:
    """Return current org's assistant settings."""
    settings = await _load_assistant_settings(session, org.id, current_user.id)
    return SettingsResponse(
        provider=settings.get("provider"),
        model=settings.get("model"),
        has_key=bool(settings.get("api_key")),
    )


# ---------------------------------------------------------------------------
# PUT /settings
# ---------------------------------------------------------------------------


@router.put("/settings")
async def update_settings(
    body: AssistantSettingsRequest,
    current_user: CurrentActiveUser,
    org: CurrentOrg,
    session: DbSession,
) -> SettingsResponse:
    """Update org's assistant settings (provider, model, optionally api_key)."""
    await _upsert_variable(session, org.id, current_user.id, "assistant.provider", body.provider)
    await _upsert_variable(session, org.id, current_user.id, "assistant.model", body.model)
    if body.api_key is not None:
        await _upsert_variable(session, org.id, current_user.id, "assistant.api_key", body.api_key)

    await session.flush()

    return SettingsResponse(
        provider=body.provider,
        model=body.model,
        has_key=body.api_key is not None or bool(
            (await session.exec(
                select(Variable).where(
                    Variable.organization_id == org.id,
                    Variable.name == "assistant.api_key",
                )
            )).first()
        ),
    )

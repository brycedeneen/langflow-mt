"""Tests for AssistantService using FakeProviderClient."""

from __future__ import annotations

from uuid import uuid4

import pytest

from langflow.services.assistant.providers.base import FakeProviderClient, ScriptedTurn, StreamEvent
from langflow.services.assistant.service import AssistantService


def _make_flow_data():
    return {"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}}


def _make_service(provider: FakeProviderClient, flow_data: dict | None = None) -> AssistantService:
    return AssistantService(
        provider_client=provider,
        flow_data=flow_data or _make_flow_data(),
        flow_id=uuid4(),
        org_id=uuid4(),
        user_id=uuid4(),
        model_name="gpt-4o",
    )


async def _collect_events(service: AssistantService, message: str) -> list[dict]:
    events = []
    async for event in service.send_message(message):
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_simple_text_response():
    """Token events stream correctly and message_complete is emitted."""
    provider = FakeProviderClient(turns=[
        ScriptedTurn(events=[
            StreamEvent(type="token", text="Hello"),
            StreamEvent(type="token", text=" world"),
            StreamEvent(type="message_complete"),
        ]),
    ])
    service = _make_service(provider)

    events = await _collect_events(service, "Hi there")

    token_events = [e for e in events if e["type"] == "token"]
    assert len(token_events) == 2
    assert token_events[0]["text"] == "Hello"
    assert token_events[1]["text"] == " world"

    complete_events = [e for e in events if e["type"] == "message_complete"]
    assert len(complete_events) == 1


@pytest.mark.asyncio
async def test_tool_call_and_response():
    """Tool call for list_categories produces tool_call, tool_result, and message_complete events."""
    provider = FakeProviderClient(turns=[
        # Turn 1: LLM wants to call a tool
        ScriptedTurn(events=[
            StreamEvent(
                type="tool_call",
                tool_call_id="call_1",
                tool_name="list_categories",
                tool_args={},
            ),
        ]),
        # Turn 2: LLM responds with text after seeing tool result
        ScriptedTurn(events=[
            StreamEvent(type="token", text="Here are the categories."),
            StreamEvent(type="message_complete"),
        ]),
    ])
    service = _make_service(provider)

    events = await _collect_events(service, "What components are available?")

    types = [e["type"] for e in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "message_complete" in types

    tool_call_event = next(e for e in events if e["type"] == "tool_call")
    assert tool_call_event["tool_name"] == "list_categories"

    tool_result_event = next(e for e in events if e["type"] == "tool_result")
    assert tool_result_event["tool_call_id"] == "call_1"


@pytest.mark.asyncio
async def test_mutation_tool_emits_flow_patch():
    """add_component tool emits a flow_patch event with added_nodes."""
    provider = FakeProviderClient(turns=[
        # Turn 1: LLM calls add_component
        ScriptedTurn(events=[
            StreamEvent(
                type="tool_call",
                tool_call_id="call_2",
                tool_name="add_component",
                tool_args={"component_type": "OpenAIModel", "position": "auto"},
            ),
        ]),
        # Turn 2: LLM responds
        ScriptedTurn(events=[
            StreamEvent(type="token", text="Added an OpenAI model."),
            StreamEvent(type="message_complete"),
        ]),
    ])
    service = _make_service(provider)

    events = await _collect_events(service, "Add an OpenAI model")

    # Verify flow_patch event exists
    flow_patch_events = [e for e in events if e["type"] == "flow_patch"]
    assert len(flow_patch_events) == 1

    patch = flow_patch_events[0]["patch"]
    assert len(patch["added_nodes"]) == 1
    assert patch["added_nodes"][0]["data"]["type"] == "OpenAIModel"

    # Verify the node was actually added to flow_data
    assert len(service.flow_data["nodes"]) == 1


@pytest.mark.asyncio
async def test_error_in_provider():
    """Error event from provider is yielded correctly."""
    provider = FakeProviderClient(turns=[
        ScriptedTurn(events=[
            StreamEvent(type="error", error_message="Rate limit exceeded"),
        ]),
    ])
    service = _make_service(provider)

    events = await _collect_events(service, "Do something")

    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["error"] == "Rate limit exceeded"

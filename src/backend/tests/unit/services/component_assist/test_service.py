"""Tests for the ComponentAssistService streaming behavior."""
from __future__ import annotations

from typing import Any, AsyncIterator
from uuid import uuid4

import pytest

from langflow.services.component_assist.schemas import (
    ComponentAssistRequest,
    NodeSnapshot,
)
from langflow.services.component_assist.service import ComponentAssistService


class _ScriptedLLM:
    """Replays a canned sequence of chunks. Exposes `.calls` for inspection."""

    def __init__(self, scripts: list[list[dict[str, Any]]]):
        self._scripts = list(scripts)
        self.calls: list[str] = []

    async def stream(self, *, system_prompt: str, thread: list, user_message: str, tools: list):
        self.calls.append(user_message)
        script = self._scripts.pop(0)

        async def _gen() -> AsyncIterator[dict[str, Any]]:
            for chunk in script:
                yield chunk

        return _gen()


def _req() -> ComponentAssistRequest:
    snap = NodeSnapshot(
        node_id="n1",
        type="FooComponent",
        display_name="Foo",
        description=None,
        template={"x": {"display_name": "X", "value": 0}},
        outputs=[],
    )
    return ComponentAssistRequest(
        flow_id=uuid4(),
        node_id="n1",
        node_snapshot=snap,
        neighbor_snapshots=[],
        thread=[],
        user_message="set x to 5",
    )


async def _collect(stream):
    return [ev async for ev in stream]


@pytest.mark.asyncio
async def test_streams_token_then_tool_call_then_done():
    llm = _ScriptedLLM([[
        {"type": "token", "text": "Setting "},
        {"type": "token", "text": "x to 5."},
        {
            "type": "tool_call",
            "name": "propose_config_update",
            "args": {"node_id": "n1", "patch": {"x": 5}, "rationale": "user asked"},
        },
    ]])
    svc = ComponentAssistService(llm=llm, guide=None)
    events = await _collect(svc.stream_reply(_req()))
    kinds = [e["type"] for e in events]
    assert kinds == ["token", "token", "tool_call", "done"]
    assert events[2]["name"] == "propose_config_update"
    assert events[2]["args"]["patch"] == {"x": 5}


@pytest.mark.asyncio
async def test_invalid_patch_keys_trigger_one_retry_then_error():
    llm = _ScriptedLLM([
        [  # first call: patch references non-existent field
            {
                "type": "tool_call",
                "name": "propose_config_update",
                "args": {"node_id": "n1", "patch": {"not_a_field": 1}, "rationale": ""},
            },
        ],
        [  # retry call: still wrong
            {
                "type": "tool_call",
                "name": "propose_config_update",
                "args": {"node_id": "n1", "patch": {"still_wrong": 1}, "rationale": ""},
            },
        ],
    ])
    svc = ComponentAssistService(llm=llm, guide=None)
    events = await _collect(svc.stream_reply(_req()))
    assert events[-1]["type"] == "error"
    assert len(llm.calls) == 2  # one retry


@pytest.mark.asyncio
async def test_node_id_mismatch_is_rejected():
    llm = _ScriptedLLM([[
        {
            "type": "tool_call",
            "name": "propose_config_update",
            "args": {"node_id": "different", "patch": {"x": 5}, "rationale": ""},
        },
    ], [
        {
            "type": "tool_call",
            "name": "propose_config_update",
            "args": {"node_id": "different", "patch": {"x": 5}, "rationale": ""},
        },
    ]])
    svc = ComponentAssistService(llm=llm, guide=None)
    events = await _collect(svc.stream_reply(_req()))
    assert events[-1]["type"] == "error"

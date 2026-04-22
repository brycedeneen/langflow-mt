"""Validation tests for ComponentAssist request/tool schemas."""
from __future__ import annotations

import pytest
from langflow.services.component_assist.schemas import (
    ComponentAssistRequest,
    NodeSnapshot,
    ProposeConfigUpdate,
    ThreadMessage,
)
from pydantic import ValidationError


def _snapshot(node_id: str = "n1", ctype: str = "DataMapperComponent") -> NodeSnapshot:
    return NodeSnapshot(
        node_id=node_id,
        type=ctype,
        display_name="Data Mapper",
        description="Maps fields",
        template={"mapping": {"display_name": "Mapping", "value": {}}},
        outputs=[{"name": "out", "types": ["Data"]}],
    )


def test_request_minimum_valid():
    req = ComponentAssistRequest(
        flow_id="11111111-1111-1111-1111-111111111111",
        node_id="n1",
        node_snapshot=_snapshot(),
        neighbor_snapshots=[],
        thread=[],
        user_message="hi",
    )
    assert req.node_id == "n1"


def test_request_rejects_empty_message():
    with pytest.raises(ValidationError):
        ComponentAssistRequest(
            flow_id="11111111-1111-1111-1111-111111111111",
            node_id="n1",
            node_snapshot=_snapshot(),
            neighbor_snapshots=[],
            thread=[],
            user_message="",
        )


def test_thread_message_roles():
    assert ThreadMessage(role="user", content="x").role == "user"
    assert ThreadMessage(role="assistant", content="x").role == "assistant"
    with pytest.raises(ValidationError):
        ThreadMessage(role="system", content="x")  # system not allowed on the wire


def test_propose_config_update_requires_node_id_and_patch():
    tool = ProposeConfigUpdate(node_id="n1", patch={"a": 1}, rationale="because")
    assert tool.patch == {"a": 1}
    with pytest.raises(ValidationError):
        ProposeConfigUpdate(node_id="n1", patch="nope", rationale="x")  # patch must be dict

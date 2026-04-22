"""Tests for the component assist prompt builder."""
from __future__ import annotations

from langflow.services.component_assist.prompt import build_system_prompt
from langflow.services.component_assist.schemas import NodeSnapshot


def _snapshot(node_id="n", ctype="FooComponent") -> NodeSnapshot:
    return NodeSnapshot(
        node_id=node_id,
        type=ctype,
        display_name="Foo",
        description="does foo",
        template={"x": {"display_name": "X", "value": 1}},
        outputs=[{"name": "out", "types": ["Data"]}],
    )


def test_prompt_includes_generic_framing_without_guide():
    prompt = build_system_prompt(
        node_snapshot=_snapshot(),
        neighbor_snapshots=[],
        guide=None,
    )
    assert "FooComponent" in prompt
    assert "display_name" in prompt  # the target node is rendered
    assert "propose_config_update" in prompt


def test_prompt_injects_guide_when_present():
    prompt = build_system_prompt(
        node_snapshot=_snapshot(),
        neighbor_snapshots=[],
        guide="Here is how you configure Foo: step 1.",
    )
    assert "Here is how you configure Foo: step 1." in prompt


def test_prompt_renders_neighbors_when_present():
    target = _snapshot("target", "Target")
    upstream = _snapshot("up", "UpstreamThing")
    prompt = build_system_prompt(
        node_snapshot=target,
        neighbor_snapshots=[upstream],
        guide=None,
    )
    assert "UpstreamThing" in prompt
    assert "neighbors" in prompt.lower()

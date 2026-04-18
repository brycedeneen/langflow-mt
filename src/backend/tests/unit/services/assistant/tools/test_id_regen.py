"""Unit tests for the node/edge id regenerator used by apply_template."""

from __future__ import annotations

from langflow.services.assistant.tools._id_regen import regenerate_flow_ids


def test_returns_fresh_ids_for_every_node():
    data = {
        "nodes": [
            {"id": "SlackNotifier-abc12", "data": {"id": "SlackNotifier-abc12", "type": "SlackNotifier"}},
            {"id": "Webhook-def34", "data": {"id": "Webhook-def34", "type": "Webhook"}},
        ],
        "edges": [],
    }
    out = regenerate_flow_ids(data)
    new_node_ids = {n["id"] for n in out["nodes"]}
    original_ids = {"SlackNotifier-abc12", "Webhook-def34"}
    assert new_node_ids.isdisjoint(original_ids)
    assert len(new_node_ids) == 2  # two unique new ids
    # node.data.id mirrors node.id
    for node in out["nodes"]:
        assert node["id"] == node["data"]["id"]
    # New ids preserve the component type prefix
    prefixes = {n["id"].split("-", 1)[0] for n in out["nodes"]}
    assert prefixes == {"SlackNotifier", "Webhook"}


def test_remaps_edge_source_target_to_new_ids():
    data = {
        "nodes": [
            {"id": "A-11111", "data": {"id": "A-11111", "type": "A"}},
            {"id": "B-22222", "data": {"id": "B-22222", "type": "B"}},
        ],
        "edges": [
            {
                "id": "reactflow__edge-A-11111handle1-B-22222handle2",
                "source": "A-11111",
                "target": "B-22222",
                "sourceHandle": "handle1",
                "targetHandle": "handle2",
            }
        ],
    }
    out = regenerate_flow_ids(data)
    a_new = next(n["id"] for n in out["nodes"] if n["data"]["type"] == "A")
    b_new = next(n["id"] for n in out["nodes"] if n["data"]["type"] == "B")
    assert out["edges"][0]["source"] == a_new
    assert out["edges"][0]["target"] == b_new
    # Edge id rebuilt to match the new sources
    assert a_new in out["edges"][0]["id"]
    assert b_new in out["edges"][0]["id"]


def test_handles_empty_flow_data():
    out = regenerate_flow_ids({"nodes": [], "edges": []})
    assert out == {"nodes": [], "edges": []}


def test_returns_a_deep_copy_not_the_input():
    data = {
        "nodes": [{"id": "X-aaaaa", "data": {"id": "X-aaaaa", "type": "X"}}],
        "edges": [],
    }
    out = regenerate_flow_ids(data)
    assert out["nodes"][0]["id"] != data["nodes"][0]["id"]
    # Original left untouched
    assert data["nodes"][0]["id"] == "X-aaaaa"

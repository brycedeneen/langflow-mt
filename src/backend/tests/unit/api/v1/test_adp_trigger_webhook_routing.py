"""Routing helpers must recognize ADP Trigger nodes as webhook-style components."""

from langflow.services.database.models.flow.utils import (
    get_all_webhook_components_in_flow,
    get_webhook_component_in_flow,
)


def _flow_with_node(node_id: str) -> dict:
    return {
        "nodes": [
            {"id": node_id, "data": {"type": node_id.split("-")[0]}},
        ],
        "edges": [],
    }


def test_detects_webhook_component_by_id():
    flow = _flow_with_node("Webhook-abc123")
    node = get_webhook_component_in_flow(flow)
    assert node is not None
    assert node["id"] == "Webhook-abc123"


def test_detects_adp_trigger_component_by_id():
    flow = _flow_with_node("ADPTrigger-xyz789")
    node = get_webhook_component_in_flow(flow)
    assert node is not None, "ADP Trigger must be treated as a webhook component"
    assert node["id"] == "ADPTrigger-xyz789"


def test_returns_none_when_no_webhook_or_adp_trigger():
    flow = _flow_with_node("Agent-abc")
    assert get_webhook_component_in_flow(flow) is None


def test_all_webhook_components_includes_both_types():
    flow = {
        "nodes": [
            {"id": "Webhook-1", "data": {}},
            {"id": "ADPTrigger-2", "data": {}},
            {"id": "Agent-3", "data": {}},
        ],
        "edges": [],
    }
    matches = get_all_webhook_components_in_flow(flow)
    ids = {n["id"] for n in matches}
    assert ids == {"Webhook-1", "ADPTrigger-2"}


def test_get_all_returns_empty_for_none_flow_data():
    assert get_all_webhook_components_in_flow(None) == []

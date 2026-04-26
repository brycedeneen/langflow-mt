"""Tests for FlowMutationTools (Task 4)."""

from __future__ import annotations

import copy

import pytest

from langflow.services.assistant.tools.mutation import FlowMutationTools

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

EMPTY_FLOW_DATA = {"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}}

FLOW_WITH_PROMPT = {
    "nodes": [
        {
            "id": "Prompt-abc12",
            "type": "genericNode",
            "position": {"x": 100, "y": 200},
            "data": {
                "type": "Prompt",
                "id": "Prompt-abc12",
                "node": {
                    "template": {"template": {"type": "str", "value": "Hello {name}"}},
                    "outputs": [{"types": ["Message"], "name": "output"}],
                },
                "output_types": ["Message"],
            },
        }
    ],
    "edges": [],
    "viewport": {"x": 0, "y": 0, "zoom": 1},
}


def _fresh_empty():
    return copy.deepcopy(EMPTY_FLOW_DATA)


def _fresh_prompt():
    return copy.deepcopy(FLOW_WITH_PROMPT)


# ---------------------------------------------------------------------------
# 1. add_component with auto position (empty flow)
# ---------------------------------------------------------------------------


async def test_add_component_auto_position_empty():
    data = _fresh_empty()
    tools = FlowMutationTools(data)
    result = await tools.add_component("ChatOpenAI")

    node_id = result["node_id"]
    assert node_id.startswith("ChatOpenAI-")
    assert len(node_id) == len("ChatOpenAI-") + 5

    added = result["applied_patch"]["added_nodes"]
    assert len(added) == 1
    assert added[0]["position"] == {"x": 100, "y": 200}


# ---------------------------------------------------------------------------
# 2. add_component with explicit position
# ---------------------------------------------------------------------------


async def test_add_component_explicit_position():
    data = _fresh_empty()
    tools = FlowMutationTools(data)
    result = await tools.add_component("Prompt", position={"x": 500, "y": 600})

    node = result["applied_patch"]["added_nodes"][0]
    assert node["position"] == {"x": 500, "y": 600}


# ---------------------------------------------------------------------------
# 3. add_component with initial_fields
# ---------------------------------------------------------------------------


async def test_add_component_initial_fields():
    data = _fresh_empty()
    tools = FlowMutationTools(data)
    result = await tools.add_component(
        "Prompt",
        initial_fields={"template": "Hello {name}", "model": "gpt-4"},
    )

    node = result["applied_patch"]["added_nodes"][0]
    tmpl = node["data"]["node"]["template"]
    assert tmpl["template"] == {"type": "str", "value": "Hello {name}"}
    assert tmpl["model"] == {"type": "str", "value": "gpt-4"}


# ---------------------------------------------------------------------------
# 4. add_component updates flow_data in place
# ---------------------------------------------------------------------------


async def test_add_component_updates_flow_data_in_place():
    data = _fresh_empty()
    tools = FlowMutationTools(data)
    assert len(data["nodes"]) == 0

    await tools.add_component("Prompt")
    assert len(data["nodes"]) == 1


# ---------------------------------------------------------------------------
# 5. connect_edge between two nodes
# ---------------------------------------------------------------------------


async def test_connect_edge():
    data = _fresh_prompt()
    tools = FlowMutationTools(data)
    # Add a second node to connect to
    await tools.add_component("ChatOpenAI")
    target_id = data["nodes"][1]["id"]

    result = tools.connect_edge("Prompt-abc12", "output", target_id, "input")

    assert result["edge_id"].startswith("reactflow__edge-")
    assert "Prompt-abc12" in result["edge_id"]
    assert len(result["applied_patch"]["added_edges"]) == 1
    assert len(data["edges"]) == 1

    edge = data["edges"][0]
    assert edge["source"] == "Prompt-abc12"
    assert edge["target"] == target_id
    # connect_edge now emits ReactFlow-style encoded handles that embed dataType,
    # node id, name and output_types — so just assert the logical name is encoded.
    assert "œnameœ:œoutputœ" in edge["sourceHandle"] or edge["sourceHandle"] == "output"
    assert "œfieldNameœ:œinputœ" in edge["targetHandle"] or edge["targetHandle"] == "input"


# ---------------------------------------------------------------------------
# 6. connect_edge raises ValueError for missing node
# ---------------------------------------------------------------------------


def test_connect_edge_missing_source():
    data = _fresh_prompt()
    tools = FlowMutationTools(data)
    with pytest.raises(ValueError, match="Source node not found"):
        tools.connect_edge("nonexistent", "output", "Prompt-abc12", "input")


def test_connect_edge_missing_target():
    data = _fresh_prompt()
    tools = FlowMutationTools(data)
    with pytest.raises(ValueError, match="Target node not found"):
        tools.connect_edge("Prompt-abc12", "output", "nonexistent", "input")


# ---------------------------------------------------------------------------
# 7. set_field_value on existing node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_field_value():
    data = _fresh_prompt()
    tools = FlowMutationTools(data)
    result = await tools.set_field_value("Prompt-abc12", "template", "Goodbye {name}")

    assert result["updated_node_id"] == "Prompt-abc12"
    assert len(result["applied_patch"]["updated_nodes"]) == 1

    # Verify the value was updated in-place
    tmpl = data["nodes"][0]["data"]["node"]["template"]["template"]
    assert tmpl["value"] == "Goodbye {name}"


@pytest.mark.asyncio
async def test_set_field_value_unknown_field_raises():
    data = _fresh_prompt()
    tools = FlowMutationTools(data)
    with pytest.raises(ValueError, match="not found on node"):
        await tools.set_field_value("Prompt-abc12", "new_field", "new_value")

    # Ensure the template wasn't mutated.
    tmpl = data["nodes"][0]["data"]["node"]["template"]
    assert "new_field" not in tmpl


# ---------------------------------------------------------------------------
# 8. set_field_value raises ValueError for missing node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_field_value_missing_node():
    data = _fresh_prompt()
    tools = FlowMutationTools(data)
    with pytest.raises(ValueError, match="Node not found"):
        await tools.set_field_value("nonexistent", "template", "value")


# ---------------------------------------------------------------------------
# 9. remove_component removes node
# ---------------------------------------------------------------------------


def test_remove_component():
    data = _fresh_prompt()
    tools = FlowMutationTools(data)
    result = tools.remove_component("Prompt-abc12")

    assert result["removed_node_id"] == "Prompt-abc12"
    assert "Prompt-abc12" in result["applied_patch"]["removed_ids"]
    assert len(data["nodes"]) == 0


# ---------------------------------------------------------------------------
# 10. remove_component also removes connected edges
# ---------------------------------------------------------------------------


async def test_remove_component_removes_connected_edges():
    data = _fresh_prompt()
    tools = FlowMutationTools(data)

    # Add two more nodes and edges
    r1 = await tools.add_component("ChatOpenAI")
    r2 = await tools.add_component("Output")
    id1 = r1["node_id"]
    id2 = r2["node_id"]

    tools.connect_edge("Prompt-abc12", "output", id1, "input")
    tools.connect_edge(id1, "response", id2, "input")

    assert len(data["edges"]) == 2

    # Remove the middle node -- should remove both edges connected to it
    result = tools.remove_component(id1)
    assert len(data["edges"]) == 0
    assert len(data["nodes"]) == 2  # Prompt + Output remain

    removed = result["applied_patch"]["removed_ids"]
    assert id1 in removed
    # Both edge IDs should also be in removed
    assert len(removed) == 3  # node + 2 edges


# ---------------------------------------------------------------------------
# 11. add_sticky_note creates noteNode
# ---------------------------------------------------------------------------


def test_add_sticky_note():
    data = _fresh_empty()
    tools = FlowMutationTools(data)
    result = tools.add_sticky_note("Remember to add error handling")

    node_id = result["node_id"]
    assert node_id.startswith("note-")

    node = result["applied_patch"]["added_nodes"][0]
    assert node["type"] == "noteNode"
    assert node["width"] == 300
    assert node["height"] == 200
    assert node["data"]["type"] == "note"
    assert node["data"]["node"]["description"] == "Remember to add error handling"
    assert len(data["nodes"]) == 1


def test_add_sticky_note_auto_position_with_existing_nodes():
    data = _fresh_prompt()
    tools = FlowMutationTools(data)
    result = tools.add_sticky_note("Note content")

    node = result["applied_patch"]["added_nodes"][0]
    # Auto position: rightmost_x(100) + 300 - 200 = 200, avg_y(200) - 150 = 50
    assert node["position"] == {"x": 200, "y": 50}

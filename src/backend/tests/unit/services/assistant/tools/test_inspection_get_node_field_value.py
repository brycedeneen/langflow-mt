from langflow.services.assistant.tools.inspection import FlowInspectionTools


def _flow_with_node(node_id: str, template_fields: dict) -> dict:
    return {
        "nodes": [
            {
                "id": node_id,
                "data": {
                    "node": {
                        "template": {
                            name: {"value": value} for name, value in template_fields.items()
                        }
                    }
                },
            }
        ],
        "edges": [],
    }


def test_get_node_field_value_returns_string_value():
    flow = _flow_with_node("trigger-1", {"endpoint": "http://example.com/webhook/abc"})
    tools = FlowInspectionTools(flow)
    assert tools.get_node_field_value("trigger-1", "endpoint") == "http://example.com/webhook/abc"


def test_get_node_field_value_returns_empty_string_when_value_empty():
    flow = _flow_with_node("trigger-1", {"endpoint": ""})
    tools = FlowInspectionTools(flow)
    assert tools.get_node_field_value("trigger-1", "endpoint") == ""


def test_get_node_field_value_returns_node_not_found_error():
    flow = _flow_with_node("trigger-1", {"endpoint": "x"})
    tools = FlowInspectionTools(flow)
    assert tools.get_node_field_value("missing-id", "endpoint") == "node not found: missing-id"


def test_get_node_field_value_returns_field_not_found_error():
    flow = _flow_with_node("trigger-1", {"endpoint": "x"})
    tools = FlowInspectionTools(flow)
    assert tools.get_node_field_value("trigger-1", "missing_field") == "field not found on node: missing_field"


def test_get_node_field_value_coerces_non_string_values_to_string():
    flow = _flow_with_node("trigger-1", {"port": 22})
    tools = FlowInspectionTools(flow)
    assert tools.get_node_field_value("trigger-1", "port") == "22"


import pytest
from langflow.services.assistant.service import AssistantService


@pytest.mark.asyncio
async def test_get_node_field_value_dispatches_to_inspection_tools():
    flow_data = {
        "nodes": [{"id": "trigger-1", "data": {"node": {"template": {"endpoint": {"value": "http://x"}}}}}],
        "edges": [],
    }
    service = AssistantService.__new__(AssistantService)
    from langflow.services.assistant.tools.inspection import FlowInspectionTools
    from langflow.services.assistant.tools.mutation import FlowMutationTools
    service.flow_data = flow_data
    service.mutation_tools = FlowMutationTools(flow_data)
    service.inspection_tools = FlowInspectionTools(flow_data)
    result = await service._execute_tool(
        "get_node_field_value", {"node_id": "trigger-1", "field_name": "endpoint"}
    )
    assert result == {"result": "http://x"}

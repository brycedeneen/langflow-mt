from langflow.services.assistant.tools.pro_services import suggest_professional_services
from langflow.services.assistant.tools.registry import (
    INSPECTION_TOOLS,
    is_inspection_tool,
)


def test_tool_is_registered_in_inspection_tools():
    names = {t["name"] for t in INSPECTION_TOOLS}
    assert "suggest_professional_services" in names
    assert is_inspection_tool("suggest_professional_services")


def test_tool_schema_has_reason_field():
    tool = next(t for t in INSPECTION_TOOLS if t["name"] == "suggest_professional_services")
    assert tool["parameters"]["required"] == ["reason"]
    assert tool["parameters"]["properties"]["reason"]["type"] == "string"


def test_handler_returns_shown_and_echo():
    result = suggest_professional_services(reason="user has been stuck on OAuth for 15 minutes")
    assert result == {"shown": True, "reason": "user has been stuck on OAuth for 15 minutes"}

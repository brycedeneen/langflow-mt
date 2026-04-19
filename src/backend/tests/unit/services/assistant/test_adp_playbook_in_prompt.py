from langflow.services.assistant.service import SYSTEM_PROMPT_TEMPLATE


def test_adp_playbook_section_present():
    assert "## ADP integration playbook" in SYSTEM_PROMPT_TEMPLATE


def test_canonical_wiring_documented():
    assert "ADP Trigger" in SYSTEM_PROMPT_TEMPLATE
    assert "Agent" in SYSTEM_PROMPT_TEMPLATE
    assert "Sink" in SYSTEM_PROMPT_TEMPLATE


def test_event_groupings_named():
    text = SYSTEM_PROMPT_TEMPLATE.lower()
    assert "new hire" in text
    assert "retirement" in text
    assert "deceased" in text


def test_bridge_agent_uses_fast_cheap_model():
    assert "haiku" in SYSTEM_PROMPT_TEMPLATE.lower()


def test_adp_worker_tools_attached():
    assert "ADP Worker Tools" in SYSTEM_PROMPT_TEMPLATE


def test_friendly_field_hints_present():
    text = SYSTEM_PROMPT_TEMPLATE.lower()
    assert "person.legalname.formattedname" in text
    assert "person.legaladdress" in text
    assert "person.communication.emails" in text


def test_output_schema_table_row_shape_documented():
    # The Agent's structured output is output_schema (TableInput),
    # not a JSON schema. The playbook must teach the row shape.
    assert "output_schema" in SYSTEM_PROMPT_TEMPLATE
    text = SYSTEM_PROMPT_TEMPLATE.lower()
    assert "name" in text and "description" in text and "type" in text and "multiple" in text


def test_tool_attach_handles_documented():
    # source output handle = "component_as_tool", target field = "tools"
    assert "component_as_tool" in SYSTEM_PROMPT_TEMPLATE
    assert "tools" in SYSTEM_PROMPT_TEMPLATE


def test_post_wiring_credentials_surfacing():
    # Use get_webhook_credentials, NOT get_node_field_value, for api_key
    assert "get_webhook_credentials" in SYSTEM_PROMPT_TEMPLATE
    assert "x-api-key" in SYSTEM_PROMPT_TEMPLATE


def test_secret_field_routing_via_create_secret_variable():
    assert "create_secret_variable" in SYSTEM_PROMPT_TEMPLATE
    text = SYSTEM_PROMPT_TEMPLATE.lower()
    assert "password" in text

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


def test_secret_routing_emphasizes_two_step_pattern():
    # Step 1 alone (create_secret_variable) doesn't wire the field. The
    # prompt must emphasize that step 2 (set_field_value) is required.
    text = SYSTEM_PROMPT_TEMPLATE.lower()
    assert "two steps" in text or "two-step" in text or "both" in text
    assert "set_field_value" in SYSTEM_PROMPT_TEMPLATE
    # The "stays empty" phrase explicitly warns about the failure mode.
    assert "stays empty" in text


def test_check_existing_variables_before_asking():
    # The assistant should check list_user_variables before re-asking
    # for credentials the user may already have configured.
    assert "list_user_variables" in SYSTEM_PROMPT_TEMPLATE


def test_adp_credentials_are_per_flow_not_shared_variables():
    # ADP creds are PER-FLOW autosecrets, not shared user Variables.
    # The playbook must direct the assistant to write the actual values
    # straight into the ADP Auth fields (paste-equivalent), NOT call
    # create_secret_variable for them.
    text = SYSTEM_PROMPT_TEMPLATE.lower()
    # The four ADP credential field names must still be named so the
    # assistant knows which fields it's wiring.
    assert "client_id" in text
    assert "client_secret" in text
    assert "client_certificate" in text
    assert "client_key" in text
    # The playbook must explicitly call out per-flow scoping for ADP.
    assert "per-flow" in text or "per flow" in text
    # And explicitly negate the create_secret_variable / user-Variable
    # pattern for ADP fields, since the general rule above the ADP block
    # mandates that pattern for other secret fields.
    assert "do not call `create_secret_variable`" in text or \
           "do not call create_secret_variable" in text


def test_check_required_fields_before_finishing():
    # Generic guideline: don't leave required fields empty at end of build.
    text = SYSTEM_PROMPT_TEMPLATE.lower()
    assert "required field" in text
    assert "get_component_schema" in SYSTEM_PROMPT_TEMPLATE

from langflow.services.assistant.service import SYSTEM_PROMPT_TEMPLATE


def test_template_override_rule_present():
    text = SYSTEM_PROMPT_TEMPLATE.lower()
    assert "template" in text and "agent_instructions" in text and "take precedence" in text


def test_template_override_falls_back_to_playbook():
    text = SYSTEM_PROMPT_TEMPLATE.lower()
    assert "fall back to" in text or "fallback to" in text

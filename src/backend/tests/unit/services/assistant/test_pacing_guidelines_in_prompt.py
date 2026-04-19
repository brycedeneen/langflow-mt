from langflow.services.assistant.service import SYSTEM_PROMPT_TEMPLATE


def test_pacing_guidelines_present():
    assert "## Conversation pacing" in SYSTEM_PROMPT_TEMPLATE


def test_pacing_rule_dont_re_ask_when_user_provided_info():
    assert "do not re-ask" in SYSTEM_PROMPT_TEMPLATE.lower()


def test_pacing_rule_one_question_at_a_time():
    assert "one question at a time" in SYSTEM_PROMPT_TEMPLATE.lower()


def test_pacing_rule_friendly_language():
    assert "friendly, non-technical language" in SYSTEM_PROMPT_TEMPLATE.lower()


def test_pacing_rule_confirm_scope_before_questions():
    assert "confirm scope" in SYSTEM_PROMPT_TEMPLATE.lower()


def test_pacing_rule_propose_defaults():
    assert "propose sensible defaults" in SYSTEM_PROMPT_TEMPLATE.lower()


def test_pacing_rule_surface_actionables_after_build():
    assert "surface anything the user must act on" in SYSTEM_PROMPT_TEMPLATE.lower()

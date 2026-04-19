"""Pin the [TEST_FAILURE] guideline in SYSTEM_PROMPT_TEMPLATE."""

from langflow.services.assistant.service import SYSTEM_PROMPT_TEMPLATE


def test_prompt_contains_test_failure_sentinel_bullet():
    assert "[TEST_FAILURE]" in SYSTEM_PROMPT_TEMPLATE
    assert "clicked \"Ask assistant\"" in SYSTEM_PROMPT_TEMPLATE


def test_prompt_contains_credential_walkthrough_keywords():
    # The guideline instructs the LLM to branch on these keywords.
    for keyword in ["credential", "auth", "api_key", "token", "invalid_auth", "401", "403"]:
        assert keyword in SYSTEM_PROMPT_TEMPLATE, f"missing keyword: {keyword}"


def test_prompt_tells_llm_to_stay_focused_on_fixing_one_failure():
    assert "do not propose redesigning the flow" in SYSTEM_PROMPT_TEMPLATE

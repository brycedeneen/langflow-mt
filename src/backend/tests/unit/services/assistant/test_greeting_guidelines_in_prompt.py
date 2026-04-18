"""Pin the four new ## Guidelines bullets in SYSTEM_PROMPT_TEMPLATE."""

from langflow.services.assistant.service import SYSTEM_PROMPT_TEMPLATE


def test_prompt_contains_greet_sentinel_bullet():
    assert "__greet__" in SYSTEM_PROMPT_TEMPLATE
    assert "opening the conversation" in SYSTEM_PROMPT_TEMPLATE


def test_prompt_contains_opinionated_narration_bullet():
    assert "make an opinionated choice and narrate it" in SYSTEM_PROMPT_TEMPLATE


def test_prompt_contains_non_technical_vocabulary_bullet():
    assert "Frame configuration in the user's terms" in SYSTEM_PROMPT_TEMPLATE


def test_prompt_contains_test_handoff_bullet():
    assert "click the Test button" in SYSTEM_PROMPT_TEMPLATE

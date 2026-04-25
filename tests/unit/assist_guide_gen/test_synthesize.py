"""Tests for LLM-backed guide synthesis."""
from __future__ import annotations

from scripts._assist_guide_gen.extract import ComponentMetadata, InputMetadata
from scripts._assist_guide_gen.synthesize import (
    build_prompt,
    synthesize_guide,
)


def _meta() -> ComponentMetadata:
    return ComponentMetadata(
        class_name="TextOperationsComponent",
        display_name="Text Operations",
        description="Run operations over text (split, join, trim).",
        documentation="https://docs.example/text-ops",
        docstring="",
        inputs=[
            InputMetadata("text", "The input text."),
            InputMetadata("operation", "Which operation to perform."),
        ],
        outputs=["result"],
    )


def test_prompt_includes_all_metadata():
    prompt = build_prompt(_meta())
    assert "Text Operations" in prompt
    assert "TextOperationsComponent" in prompt
    assert "split" in prompt
    assert "operation" in prompt


def test_synthesize_calls_llm_and_returns_text():
    recorded: list[str] = []

    def fake_llm(prompt: str) -> str:
        recorded.append(prompt)
        return "Synthesized guide body."

    guide = synthesize_guide(_meta(), llm=fake_llm)
    assert guide == "Synthesized guide body."
    assert "TextOperationsComponent" in recorded[0]


def test_synthesize_falls_back_when_llm_returns_empty():
    fake_llm = lambda _prompt: ""  # noqa: E731
    guide = synthesize_guide(_meta(), llm=fake_llm)
    # Fallback uses the description so the YAML entry isn't literally empty.
    assert "Text Operations" in guide
    assert "split" in guide.lower()

"""Tests for prompt construction + fallback behavior."""
# ruff: noqa: S101  # asserts are the standard pytest pattern
from __future__ import annotations

from scripts._agent_metadata_gen.peers import PeerEntry
from scripts._agent_metadata_gen.synthesize import (
    build_summary_prompt,
    build_usage_notes_prompt,
    fallback_summary,
    fallback_usage_notes,
    synthesize_pair,
)
from scripts._assist_guide_gen.extract import ComponentMetadata, InputMetadata


def _meta(*, class_name="Comp", inputs=None, outputs=None):
    return ComponentMetadata(
        class_name=class_name,
        display_name="Comp Display",
        description="A comp.",
        documentation=None,
        docstring="",
        inputs=inputs or [],
        outputs=outputs or [],
    )


def test_summary_prompt_includes_class_inputs_outputs_and_peers():
    meta = _meta(
        inputs=[InputMetadata(name="prompt", info="user prompt", required=True)],
        outputs=["text"],
    )
    peers = [PeerEntry("Other", "models", "Other Comp", "does other")]
    prompt = build_summary_prompt(meta, peers, exclude="Comp")
    assert "Comp" in prompt
    assert "prompt" in prompt
    assert "text" in prompt
    assert "- Other — Other Comp — does other" in prompt
    assert "Comp Display" in prompt


def test_summary_prompt_excludes_self_from_peers():
    meta = _meta(class_name="Comp")
    peers = [
        PeerEntry("Comp", "models", "Comp Display", "self should not appear"),
        PeerEntry("Other", "models", "Other Comp", "does other"),
    ]
    prompt = build_summary_prompt(meta, peers, exclude="Comp")
    assert "self should not appear" not in prompt
    assert "Other" in prompt


def test_summary_prompt_handles_empty_peers():
    meta = _meta()
    prompt = build_summary_prompt(meta, [], exclude="Comp")
    assert "(no peers in this category)" in prompt


def test_usage_notes_prompt_marks_secret_and_advanced_inputs():
    """The prompt block exposes field_type/required/advanced so the LLM can decide which to bullet."""
    meta = _meta(
        inputs=[
            InputMetadata(name="prompt", info="user prompt", field_type="MessageTextInput", required=True),
            InputMetadata(name="api_key", info="LLM key", field_type="SecretStrInput", required=True),
            InputMetadata(name="advanced_knob", info="rare", field_type="IntInput", advanced=True),
        ],
    )
    prompt = build_usage_notes_prompt(meta)
    assert "SecretStrInput" in prompt
    assert "advanced=True" in prompt or "advanced=true" in prompt.lower()
    assert "required=True" in prompt or "required=true" in prompt.lower()
    assert "## What it does" in prompt
    assert "## Inputs to ask about" in prompt
    assert "## Outputs" in prompt
    assert "## Notes" in prompt


def test_fallback_summary_uses_display_name_and_description():
    meta = _meta(class_name="StructuredOutput")
    out = fallback_summary(meta)
    assert "Comp Display" in out
    assert "A comp." in out


def test_fallback_usage_notes_emits_all_four_headings():
    meta = _meta(
        inputs=[InputMetadata(name="prompt", info="user prompt", required=True)],
        outputs=["text"],
    )
    out = fallback_usage_notes(meta)
    assert "## What it does" in out
    assert "## Inputs to ask about" in out
    assert "## Outputs" in out
    assert "## Notes" in out
    assert "**prompt**" in out
    assert "**text**" in out


def test_synthesize_pair_uses_fallback_when_llm_returns_empty():
    """Both LLM calls return ''; both fallbacks fire and are tagged in status."""
    meta = _meta()
    def _llm(_prompt: str) -> str:
        return ""
    summary, summary_status, notes, notes_status = synthesize_pair(
        meta, peers=[], llm=_llm,
    )
    assert "Comp Display" in summary
    assert summary_status == "fallback-used"
    assert "## What it does" in notes
    assert notes_status == "fallback-used"


def test_synthesize_pair_uses_llm_when_response_is_nonempty():
    meta = _meta()
    def _llm(prompt: str) -> str:
        if "configuration notes" in prompt:
            return "## What it does\nx\n## Inputs to ask about\n_None._\n## Outputs\n_None._\n## Notes\n_None._"
        return "Generated summary."
    summary, summary_status, notes, notes_status = synthesize_pair(
        meta, peers=[], llm=_llm,
    )
    assert summary == "Generated summary."
    assert summary_status == "generated"
    assert "## What it does" in notes
    assert notes_status == "generated"


def test_synthesize_pair_mixed_outcomes():
    """One field generates, the other falls back."""
    meta = _meta()
    def _llm(prompt: str) -> str:
        return "Generated summary." if "summary of this component" in prompt else ""
    _summary, summary_status, _notes, notes_status = synthesize_pair(
        meta, peers=[], llm=_llm,
    )
    assert summary_status == "generated"
    assert notes_status == "fallback-used"

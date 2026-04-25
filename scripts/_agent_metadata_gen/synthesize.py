"""Prompt construction + LLM call orchestration for component agent metadata."""
from __future__ import annotations

import textwrap
from collections.abc import Callable
from typing import TYPE_CHECKING, Literal

from scripts._agent_metadata_gen.peers import PeerEntry, format_peers_block

if TYPE_CHECKING:
    from scripts._assist_guide_gen.extract import ComponentMetadata

LLMCall = Callable[[str], str]
FieldStatus = Literal["generated", "fallback-used", "errored"]


_SUMMARY_PROMPT_TEMPLATE = """\
Write a 1-3 sentence summary of this component for an AI assistant
choosing it from a list of candidates.

Sentence 1 (required): what the component does. Be concrete - name the
thing it produces, transforms, or connects to.

Sentence 2 (optional): when this is a good fit, or what it pairs with.

Sentence 3 (optional, ONLY when one or more peers below genuinely
overlaps): the tradeoff. Format: "Prefer over <peer display name> when ...".
Use this only when you can articulate a clear, one-line "use this when ... /
use the peer when ..." distinction. If no peer materially overlaps, omit
sentence 3 - do not write filler.

Rules:
- Second person ("you help the user...").
- Don't repeat the display name verbatim.
- Don't invent capabilities not in the metadata.
- No marketing language. No markdown.
- 30-120 words. Return only the summary text.

Component metadata:
- Class: {class_name}
- Display name: {display_name}
- Description: {description}
- Documentation URL: {documentation}
- Class docstring: {docstring}
- Inputs ({input_count}):
{inputs}
- Outputs: {outputs}

Other components in the same category (peers):
{peers}
"""


_USAGE_NOTES_PROMPT_TEMPLATE = """\
Write configuration notes for an AI assistant configuring this
component. Use this exact markdown structure - emit each heading even
if a section is empty (write `_None._` in that case):

## What it does
One short paragraph (1-3 sentences).

## Inputs to ask about
- **<input_name>** - what to ask the user, plus a suggested default if
  one is obvious from the metadata.
- (one bullet per non-trivial input - skip inputs marked
  advanced=True unless they are commonly required; skip inputs whose
  field_type is SecretStrInput, since the assistant uses a separate
  variable-creation flow for those)

## Outputs
- **<output_name>** - what it produces and what it commonly feeds
  into.

## Notes
- Gotchas, constraints, or pairings worth flagging. Use `_None._` if
  nothing notable.

Rules:
- Second person ("ask the user...").
- Don't invent capabilities not in the metadata.
- One line per bullet - keep it scannable.
- 120-300 words.
- Return only the markdown body. No preamble, no fencing.

Component metadata:
- Class: {class_name}
- Display name: {display_name}
- Description: {description}
- Documentation URL: {documentation}
- Class docstring: {docstring}
- Inputs ({input_count}):
{inputs}
- Outputs: {outputs}
"""


def _format_inputs(meta: ComponentMetadata) -> str:
    if not meta.inputs:
        return "  (no declared inputs)"
    lines = []
    for i in meta.inputs:
        info = (i.info or "").replace("\n", " ").strip() or "(no description)"
        ftype = i.field_type or "Input"
        lines.append(
            f"  - {i.name} [field_type={ftype}, required={i.required}, advanced={i.advanced}]: {info}"
        )
    return "\n".join(lines)


def build_summary_prompt(
    meta: ComponentMetadata,
    peers: list[PeerEntry],
    *,
    exclude: str,
) -> str:
    return _SUMMARY_PROMPT_TEMPLATE.format(
        class_name=meta.class_name,
        display_name=meta.display_name or "(unnamed)",
        description=meta.description or "(no description)",
        documentation=meta.documentation or "(none)",
        docstring=meta.docstring or "(none)",
        input_count=len(meta.inputs),
        inputs=_format_inputs(meta),
        outputs=", ".join(meta.outputs) or "(none declared)",
        peers=format_peers_block(peers, exclude=exclude),
    )


def build_usage_notes_prompt(meta: ComponentMetadata) -> str:
    return _USAGE_NOTES_PROMPT_TEMPLATE.format(
        class_name=meta.class_name,
        display_name=meta.display_name or "(unnamed)",
        description=meta.description or "(no description)",
        documentation=meta.documentation or "(none)",
        docstring=meta.docstring or "(none)",
        input_count=len(meta.inputs),
        inputs=_format_inputs(meta),
        outputs=", ".join(meta.outputs) or "(none declared)",
    )


def fallback_summary(meta: ComponentMetadata) -> str:
    parts = [f"You help users with {meta.display_name or meta.class_name}."]
    if meta.description:
        parts.append(meta.description)
    return textwrap.fill(" ".join(parts), width=100)


def fallback_usage_notes(meta: ComponentMetadata) -> str:
    inputs_section_lines: list[str] = []
    for i in meta.inputs:
        if i.field_type == "SecretStrInput":
            continue
        if i.advanced and not i.required:
            continue
        prompt_text = (i.info or "").strip() or f"the value for `{i.name}`"
        inputs_section_lines.append(f"- **{i.name}** — ask the user for {prompt_text}.")
    if not inputs_section_lines:
        inputs_section_lines = ["_None._"]

    outputs_lines = [f"- **{name}** — produces upstream-typed output." for name in meta.outputs]
    if not outputs_lines:
        outputs_lines = ["_None._"]

    return (
        f"## What it does\n{meta.description or '(no description)'}\n\n"
        "## Inputs to ask about\n" + "\n".join(inputs_section_lines) + "\n\n"
        "## Outputs\n" + "\n".join(outputs_lines) + "\n\n"
        "## Notes\n_None._"
    )


def synthesize_pair(
    meta: ComponentMetadata,
    *,
    peers: list[PeerEntry],
    llm: LLMCall,
) -> tuple[str, FieldStatus, str, FieldStatus]:
    """Run the two LLM calls. Each falls back independently when the response is empty.

    Returns:
        ``(summary, summary_status, usage_notes, usage_notes_status)``.
    """
    summary_prompt = build_summary_prompt(meta, peers, exclude=meta.class_name)
    notes_prompt = build_usage_notes_prompt(meta)

    summary_raw = (llm(summary_prompt) or "").strip()
    if summary_raw:
        summary, summary_status = summary_raw, "generated"
    else:
        summary, summary_status = fallback_summary(meta), "fallback-used"

    notes_raw = (llm(notes_prompt) or "").strip()
    if notes_raw:
        notes, notes_status = notes_raw, "generated"
    else:
        notes, notes_status = fallback_usage_notes(meta), "fallback-used"

    return summary, summary_status, notes, notes_status

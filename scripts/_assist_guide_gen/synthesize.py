"""LLM-backed synthesis of assist guides from extracted metadata."""
from __future__ import annotations

import textwrap
from typing import Callable

from scripts._assist_guide_gen.extract import ComponentMetadata

LLMCall = Callable[[str], str]

_PROMPT_TEMPLATE = """\
You write short, useful configuration guides for individual components in a visual flow
builder. Each guide will be injected into the system prompt of an AI assistant that helps
users configure one instance of the component.

Write a 1–2 paragraph guide for this component. Cover:
- What the component does (one sentence).
- When the user should adjust which inputs, and what the inputs mean.
- Any notable constraints or gotchas inferable from the metadata.

Rules:
- Write in second person ("you help the user ...").
- Do not invent capabilities not present in the metadata.
- Do not repeat the display name or description verbatim — extract value from the inputs.
- No markdown headings; plain prose.
- 80–220 words.

Component metadata:
- Class: {class_name}
- Display name: {display_name}
- Description: {description}
- Documentation URL: {documentation}
- Class docstring: {docstring}
- Inputs ({input_count}):
{inputs}
- Outputs: {outputs}

Return ONLY the guide prose. No preamble, no closing, no markdown fencing.
"""


def _format_inputs(meta: ComponentMetadata) -> str:
    if not meta.inputs:
        return "  (no declared inputs)"
    lines = []
    for i in meta.inputs:
        info = i.info.replace("\n", " ").strip() if i.info else "(no description)"
        lines.append(f"  - {i.name}: {info}")
    return "\n".join(lines)


def build_prompt(meta: ComponentMetadata) -> str:
    return _PROMPT_TEMPLATE.format(
        class_name=meta.class_name,
        display_name=meta.display_name or "(unnamed)",
        description=meta.description or "(no description)",
        documentation=meta.documentation or "(none)",
        docstring=meta.docstring or "(none)",
        input_count=len(meta.inputs),
        inputs=_format_inputs(meta),
        outputs=", ".join(meta.outputs) or "(none declared)",
    )


def _fallback_guide(meta: ComponentMetadata) -> str:
    parts = [
        f"You help the user configure the {meta.display_name or meta.class_name} component.",
    ]
    if meta.description:
        parts.append(meta.description)
    if meta.inputs:
        names = ", ".join(i.name for i in meta.inputs if i.info or i.name)
        parts.append(f"Key inputs: {names}. Ask the user which they need to adjust.")
    return textwrap.fill(" ".join(parts), width=100)


def synthesize_guide(meta: ComponentMetadata, *, llm: LLMCall) -> str:
    prompt = build_prompt(meta)
    result = (llm(prompt) or "").strip()
    if not result:
        return _fallback_guide(meta)
    return result

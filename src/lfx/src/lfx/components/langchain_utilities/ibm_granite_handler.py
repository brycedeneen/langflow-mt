"""Compatibility shim — IBM Granite helpers are being removed (Phase 1).

Full removal is deferred to Phase 2 of the watsonx migration (see
docs/superpowers/plans/2026-04-22-watsonx-removal.md). For now this module
exports no-op stubs so `tool_calling.py` continues to import cleanly; at
runtime `is_granite_model` always returns False, so the IBM-specific branches
are short-circuited and the component falls back to its default behaviour.
"""

from __future__ import annotations

from typing import Any


def is_watsonx_model(llm: Any) -> bool:  # noqa: ARG001
    return False


def is_granite_model(llm: Any) -> bool:  # noqa: ARG001
    return False


def get_enhanced_system_prompt(base_prompt: str, tools: list) -> str:  # noqa: ARG001
    return base_prompt


def create_granite_agent(llm: Any, tools: list, prompt: Any, forced_iterations: int = 2):  # noqa: ARG001
    msg = "IBM Granite agent support has been removed."
    raise RuntimeError(msg)

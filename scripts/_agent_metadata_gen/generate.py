"""Core generator logic, importable from tests."""
from __future__ import annotations

from typing import Literal

from langflow.services.component_assist.guide_registry import is_assist_enabled

Outcome = Literal[
    "processed", "skipped-opted-out", "skipped-legacy", "skipped-existing"
]


def decide_outcome(
    cls: type,
    *,
    existing_types: set[str],
    overwrite: bool,
) -> Outcome:
    """Apply the per-class filter rules in priority order."""
    if not is_assist_enabled(cls):
        return "skipped-opted-out"
    if getattr(cls, "legacy", False):
        return "skipped-legacy"
    if cls.__name__ in existing_types and not overwrite:
        return "skipped-existing"
    return "processed"

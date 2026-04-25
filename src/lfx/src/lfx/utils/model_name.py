"""Resolve a string model identifier from the various shapes a Component
attribute can hold (ModelInput stores list-of-dicts; some flows store a
plain string; assistant flows occasionally use ``model`` instead of
``name`` as the dict key)."""

from __future__ import annotations

from typing import Any


def extract_model_name(value: Any) -> str | None:
    """Return a string model id (e.g. ``"claude-haiku-4-5-20251001"``)
    extracted from value, or ``None`` if no usable id can be found.

    Supported shapes:
      - ``None`` -> ``None``
      - ``str`` -> trimmed string (``None`` if empty/whitespace)
      - ``dict`` -> ``name`` then ``model``
      - ``list`` -> first element (string or dict, recursive)

    Deliberately does NOT fall back to ``provider`` -- provider labels like
    ``"Anthropic"`` are not litellm pricing keys, and returning them would
    silently mis-price runs.
    """
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if isinstance(value, dict):
        return _str_or_none(value.get("name") or value.get("model"))
    if isinstance(value, list):
        for item in value:
            resolved = extract_model_name(item)
            if resolved:
                return resolved
        return None
    return None


def _str_or_none(s: Any) -> str | None:
    if s is None:
        return None
    cleaned = str(s).strip()
    return cleaned or None

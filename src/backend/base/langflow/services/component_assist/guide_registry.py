"""Resolve a component's assist guide.

Resolution order:
1. `assist_guide: ClassVar[str]` attribute on the class (highest priority).
2. YAML bundle under ``guides/*.yaml`` keyed by class name (populated by the
   bulk generator — see Plan 2).
3. ``None`` — callers fall back to a generic system prompt.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_GUIDES_DIR = Path(__file__).parent / "guides"
_cached_bundle: dict[str, str] | None = None


def _load_yaml_bundle() -> dict[str, str]:
    """Load and merge every ``*.yaml`` file under ``_GUIDES_DIR``. Cached for the process."""
    global _cached_bundle  # noqa: PLW0603
    if _cached_bundle is not None:
        return _cached_bundle

    merged: dict[str, str] = {}
    if _GUIDES_DIR.is_dir():
        for path in sorted(_GUIDES_DIR.glob("*.yaml")):
            try:
                raw: Any = yaml.safe_load(path.read_text()) or []
            except yaml.YAMLError:
                logger.warning("Skipping malformed guide YAML: %s", path)
                continue
            if not isinstance(raw, list):
                continue
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                component_type = entry.get("type")
                guide = entry.get("guide")
                if isinstance(component_type, str) and isinstance(guide, str):
                    merged[component_type] = guide
    _cached_bundle = merged
    return merged


def resolve(component_cls: type) -> str | None:
    """Return the guide for a component class, or ``None`` if none configured."""
    inline = getattr(component_cls, "assist_guide", None)
    if isinstance(inline, str) and inline.strip():
        return inline
    return _load_yaml_bundle().get(component_cls.__name__)


def is_assist_enabled(component_cls: type) -> bool:
    """Return ``False`` only when the class explicitly opts out via ``assist_enabled = False``.

    Components opt out when they ship their own bespoke assistant (e.g., DataMapperComponent).
    """
    value = getattr(component_cls, "assist_enabled", True)
    return bool(value)


def reset_cache() -> None:
    """Test helper — drop the cached YAML bundle."""
    global _cached_bundle  # noqa: PLW0603
    _cached_bundle = None

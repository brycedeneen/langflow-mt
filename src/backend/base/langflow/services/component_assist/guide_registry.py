"""Resolve a component's assist guide.

Resolution order:
1. ``component_metadata.agent_usage_notes`` in the DB (admin-editable).
2. ``assist_guide: ClassVar[str]`` attribute on the class (legacy).
3. YAML bundle under ``guides/*.yaml`` keyed by class name (legacy).
4. ``None`` — callers fall back to a generic system prompt.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from langflow.services.assistant.tools.metadata_lookup import (
    fetch_component_usage_notes,
)

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


async def resolve(component_cls: type) -> str | None:
    """Return the guide for a component class, or ``None`` if none configured.

    Resolution order: DB (component_metadata.agent_usage_notes) -> class attr
    ``assist_guide`` -> YAML bundle -> ``None``.
    """
    # 1. DB lookup (component_metadata.agent_usage_notes).
    db_value = await fetch_component_usage_notes(component_cls.__name__)
    if isinstance(db_value, str) and db_value.strip():
        return db_value

    # 2. Class attribute (legacy inline guide).
    inline = getattr(component_cls, "assist_guide", None)
    if isinstance(inline, str) and inline.strip():
        return inline

    # 3. YAML bundle (legacy bundle).
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

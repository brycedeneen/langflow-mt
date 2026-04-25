"""Tests for the component assist guide registry."""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from langflow.services.component_assist import guide_registry


class _FakeWithGuide:
    assist_guide: ClassVar[str] = "inline guide for fake component"


class _FakeWithoutGuide:
    pass


@pytest.mark.asyncio
async def test_class_attribute_takes_priority(monkeypatch: pytest.MonkeyPatch):
    # Even if YAML says otherwise, class attribute wins.
    async def _no_row(_name: str) -> str | None:
        return None
    monkeypatch.setattr(
        "langflow.services.component_assist.guide_registry.fetch_component_usage_notes", _no_row,
    )
    monkeypatch.setattr(
        guide_registry,
        "_load_yaml_bundle",
        lambda: {"_FakeWithGuide": "yaml override should not win"},
    )
    assert await guide_registry.resolve(_FakeWithGuide) == "inline guide for fake component"


@pytest.mark.asyncio
async def test_yaml_bundle_fallback(monkeypatch: pytest.MonkeyPatch):
    async def _no_row(_name: str) -> str | None:
        return None
    monkeypatch.setattr(
        "langflow.services.component_assist.guide_registry.fetch_component_usage_notes", _no_row,
    )
    monkeypatch.setattr(
        guide_registry,
        "_load_yaml_bundle",
        lambda: {"_FakeWithoutGuide": "yaml guide body"},
    )
    assert await guide_registry.resolve(_FakeWithoutGuide) == "yaml guide body"


@pytest.mark.asyncio
async def test_returns_none_when_nothing_found(monkeypatch: pytest.MonkeyPatch):
    async def _no_row(_name: str) -> str | None:
        return None
    monkeypatch.setattr(
        "langflow.services.component_assist.guide_registry.fetch_component_usage_notes", _no_row,
    )
    monkeypatch.setattr(guide_registry, "_load_yaml_bundle", lambda: {})
    assert await guide_registry.resolve(_FakeWithoutGuide) is None


class _FakeOptedOut:
    assist_enabled: ClassVar[bool] = False


def test_is_assist_enabled_defaults_true():
    assert guide_registry.is_assist_enabled(_FakeWithoutGuide) is True


def test_is_assist_enabled_honors_class_attribute():
    assert guide_registry.is_assist_enabled(_FakeOptedOut) is False


def test_yaml_bundle_loads_and_merges(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "a.yaml").write_text("- type: A\n  guide: from-a\n")
    (tmp_path / "b.yaml").write_text("- type: B\n  guide: from-b\n")
    monkeypatch.setattr(guide_registry, "_GUIDES_DIR", tmp_path)
    guide_registry._cached_bundle = None  # bust cache
    bundle = guide_registry._load_yaml_bundle()
    assert bundle == {"A": "from-a", "B": "from-b"}


def test_yaml_bundle_skips_malformed_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """A malformed YAML file must not crash the loader — skip it and continue."""
    (tmp_path / "good.yaml").write_text("- type: Good\n  guide: from-good\n")
    (tmp_path / "bad.yaml").write_text("this: is: not: valid: yaml: [\n")
    monkeypatch.setattr(guide_registry, "_GUIDES_DIR", tmp_path)
    guide_registry._cached_bundle = None
    with caplog.at_level("WARNING", logger="langflow.services.component_assist.guide_registry"):
        bundle = guide_registry._load_yaml_bundle()
    assert bundle == {"Good": "from-good"}
    assert any("bad.yaml" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_db_lookup_takes_priority_over_class_attribute(monkeypatch: pytest.MonkeyPatch):
    """A non-empty agent_usage_notes in the DB beats an inline assist_guide class attr."""
    async def _fake_db_lookup(name: str) -> str | None:
        return "from-db" if name == "_FakeWithGuide" else None

    monkeypatch.setattr(
        "langflow.services.component_assist.guide_registry.fetch_component_usage_notes",
        _fake_db_lookup,
    )
    monkeypatch.setattr(
        guide_registry,
        "_load_yaml_bundle",
        lambda: {"_FakeWithGuide": "yaml override should not win either"},
    )
    assert await guide_registry.resolve(_FakeWithGuide) == "from-db"


@pytest.mark.asyncio
async def test_db_lookup_falls_through_when_null(monkeypatch: pytest.MonkeyPatch):
    """When DB returns None, the class-attribute path still wins."""
    async def _no_row(_name: str) -> str | None:
        return None

    monkeypatch.setattr(
        "langflow.services.component_assist.guide_registry.fetch_component_usage_notes",
        _no_row,
    )
    monkeypatch.setattr(guide_registry, "_load_yaml_bundle", dict)
    assert await guide_registry.resolve(_FakeWithGuide) == "inline guide for fake component"


@pytest.mark.asyncio
async def test_db_lookup_falls_through_when_empty_string(monkeypatch: pytest.MonkeyPatch):
    """Empty string in DB is treated as no content; falls through to next step."""
    async def _empty(_name: str) -> str | None:
        return "   "

    monkeypatch.setattr(
        "langflow.services.component_assist.guide_registry.fetch_component_usage_notes",
        _empty,
    )
    monkeypatch.setattr(guide_registry, "_load_yaml_bundle", lambda: {"_FakeWithoutGuide": "yaml"})
    assert await guide_registry.resolve(_FakeWithoutGuide) == "yaml"

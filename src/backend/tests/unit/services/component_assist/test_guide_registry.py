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


def test_class_attribute_takes_priority(monkeypatch: pytest.MonkeyPatch):
    # Even if YAML says otherwise, class attribute wins.
    monkeypatch.setattr(
        guide_registry,
        "_load_yaml_bundle",
        lambda: {"_FakeWithGuide": "yaml override should not win"},
    )
    assert guide_registry.resolve(_FakeWithGuide) == "inline guide for fake component"


def test_yaml_bundle_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        guide_registry,
        "_load_yaml_bundle",
        lambda: {"_FakeWithoutGuide": "yaml guide body"},
    )
    assert guide_registry.resolve(_FakeWithoutGuide) == "yaml guide body"


def test_returns_none_when_nothing_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(guide_registry, "_load_yaml_bundle", lambda: {})
    assert guide_registry.resolve(_FakeWithoutGuide) is None


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

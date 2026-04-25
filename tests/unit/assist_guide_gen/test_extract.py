"""Tests for per-class metadata extraction."""
from __future__ import annotations

from typing import ClassVar

from scripts._assist_guide_gen.extract import (
    ComponentMetadata,
    extract_metadata,
    metadata_completeness,
)


class _FakeInput:
    def __init__(self, name: str, info: str | None = None):
        self.name = name
        self.info = info


class _Rich:
    """Rich component docstring."""

    display_name = "Rich Widget"
    description = "Does rich things."
    documentation = "https://example/rich"
    inputs: ClassVar = [
        _FakeInput("alpha", info="First input."),
        _FakeInput("beta", info="Second input."),
    ]


class _Thin:
    display_name = "Thin"
    description = ""
    inputs: ClassVar = [_FakeInput("x", info=None)]


def test_extracts_rich_metadata():
    meta = extract_metadata(_Rich)
    assert meta.display_name == "Rich Widget"
    assert meta.description == "Does rich things."
    assert meta.documentation == "https://example/rich"
    assert meta.docstring.startswith("Rich component")
    assert [(i.name, i.info) for i in meta.inputs] == [
        ("alpha", "First input."),
        ("beta", "Second input."),
    ]


def test_extracts_thin_metadata():
    meta = extract_metadata(_Thin)
    assert meta.display_name == "Thin"
    assert meta.description == ""
    assert meta.inputs[0].info is None


def test_completeness_flags_thin_metadata():
    assert metadata_completeness(extract_metadata(_Rich)) == "rich"
    assert metadata_completeness(extract_metadata(_Thin)) == "thin"

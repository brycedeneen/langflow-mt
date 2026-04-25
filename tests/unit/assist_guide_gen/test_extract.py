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


def test_extract_metadata_captures_field_type_required_advanced():
    class _Input:
        def __init__(self, name, info=None, *, required=False, advanced=False):
            self.name = name
            self.info = info
            self.required = required
            self.advanced = advanced
            # Mimics SecretStrInput / TableInput / etc. Subclass name surfaces via type().__name__.
        @property
        def field_type(self):
            return type(self).__name__

    class _SecretStrInput(_Input):
        pass

    class _Comp:
        display_name = "Comp"
        description = "desc"
        documentation = ""
        inputs = [
            _Input(name="prompt", info="user prompt", required=True),
            _SecretStrInput(name="api_key", info="LLM key", required=True),
            _Input(name="advanced_knob", info="rare knob", advanced=True),
        ]
        outputs = []

    meta = extract_metadata(_Comp)
    assert [(i.name, i.field_type, i.required, i.advanced) for i in meta.inputs] == [
        ("prompt", "_Input", True, False),
        ("api_key", "_SecretStrInput", True, False),
        ("advanced_knob", "_Input", False, True),
    ]

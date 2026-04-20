import pytest
from pydantic import ValidationError

from lfx.custom.custom_component.changelog import ChangelogEntry


class TestChangelogEntry:
    def test_minimal_fields(self):
        entry = ChangelogEntry(version=1, changes="Initial release")
        assert entry.version == 1
        assert entry.changes == "Initial release"
        assert entry.notes is None

    def test_with_notes(self):
        entry = ChangelogEntry(
            version=2,
            changes="Renamed `api_key` to `auth_token`.",
            notes="Re-enter your key under Bearer Token.",
        )
        assert entry.notes == "Re-enter your key under Bearer Token."

    def test_changes_required(self):
        with pytest.raises(ValidationError):
            ChangelogEntry(version=1)  # type: ignore[call-arg]

    def test_version_must_be_int(self):
        with pytest.raises(ValidationError):
            ChangelogEntry(version="1", changes="x")  # type: ignore[arg-type]

    def test_model_dump_includes_null_notes(self):
        entry = ChangelogEntry(version=1, changes="x")
        dumped = entry.model_dump()
        assert dumped == {"version": 1, "changes": "x", "notes": None}


import logging

from lfx.custom.custom_component.changelog import validate_changelog


class _Holder:
    """Stand-in for a Component subclass during validation tests."""

    __name__ = "StubComponent"
    version = 0
    changelog: list[ChangelogEntry] = []


class TestValidateChangelog:
    def test_happy_path_no_warnings(self, caplog):
        cls = type(
            "C",
            (_Holder,),
            {
                "version": 2,
                "changelog": [
                    ChangelogEntry(version=1, changes="x"),
                    ChangelogEntry(version=2, changes="y"),
                ],
            },
        )
        with caplog.at_level(logging.WARNING):
            validate_changelog(cls)
        assert not caplog.records

    def test_warns_when_entry_version_exceeds_class_version(self, caplog):
        cls = type(
            "C",
            (_Holder,),
            {
                "version": 1,
                "changelog": [ChangelogEntry(version=3, changes="x")],
            },
        )
        with caplog.at_level(logging.WARNING):
            validate_changelog(cls)
        assert any("exceeds class version" in r.message for r in caplog.records)

    def test_warns_on_duplicate_versions(self, caplog):
        cls = type(
            "C",
            (_Holder,),
            {
                "version": 2,
                "changelog": [
                    ChangelogEntry(version=1, changes="x"),
                    ChangelogEntry(version=1, changes="y"),
                ],
            },
        )
        with caplog.at_level(logging.WARNING):
            validate_changelog(cls)
        assert any("duplicate version" in r.message for r in caplog.records)

    def test_warns_on_non_positive_entry_version(self, caplog):
        cls = type(
            "C",
            (_Holder,),
            {
                "version": 1,
                "changelog": [ChangelogEntry(version=0, changes="x")],
            },
        )
        with caplog.at_level(logging.WARNING):
            validate_changelog(cls)
        assert any("must be >= 1" in r.message for r in caplog.records)

    def test_skips_when_changelog_empty(self, caplog):
        cls = _Holder
        with caplog.at_level(logging.WARNING):
            validate_changelog(cls)
        assert not caplog.records


from typing import ClassVar

from lfx.custom.custom_component.component import Component


class TestComponentVersionAttrs:
    def test_defaults(self):
        class Plain(Component):
            display_name = "Plain"

        assert Plain.version == 0
        assert Plain.changelog == []

    def test_subclass_can_override(self):
        class Versioned(Component):
            display_name = "Versioned"
            version: int = 2
            changelog: ClassVar[list[ChangelogEntry]] = [
                ChangelogEntry(version=1, changes="Initial"),
                ChangelogEntry(version=2, changes="Second"),
            ]

        assert Versioned.version == 2
        assert len(Versioned.changelog) == 2

    def test_subclass_triggers_validation_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            class Bad(Component):
                display_name = "Bad"
                version: int = 1
                changelog: ClassVar[list[ChangelogEntry]] = [
                    ChangelogEntry(version=5, changes="x"),
                ]
        assert any("exceeds class version" in r.message for r in caplog.records)


from lfx.custom.utils import build_custom_component_template

_VC_CODE = """
from langflow.custom import Component

class VC(Component):
    display_name = "VC"

    def build(self):
        return "ok"
"""

_PLAIN_CODE = """
from langflow.custom import Component

class Plain(Component):
    display_name = "Plain"

    def build(self):
        return "ok"
"""


class TestBuilderPropagation:
    def test_version_and_changelog_emitted(self):
        class VC(Component):
            display_name = "VC"
            version: int = 2
            changelog: ClassVar[list[ChangelogEntry]] = [
                ChangelogEntry(version=1, changes="a"),
                ChangelogEntry(version=2, changes="b", notes="do X"),
            ]

            def build(self):
                return "ok"

        instance = VC(_code=_VC_CODE)
        frontend_dict, _ = build_custom_component_template(instance)
        assert frontend_dict["version"] == 2
        assert frontend_dict["changelog"] == [
            {"version": 1, "changes": "a", "notes": None},
            {"version": 2, "changes": "b", "notes": "do X"},
        ]

    def test_defaults_when_unset(self):
        class Plain(Component):
            display_name = "Plain"

            def build(self):
                return "ok"

        instance = Plain(_code=_PLAIN_CODE)
        frontend_dict, _ = build_custom_component_template(instance)
        assert frontend_dict["version"] == 0
        assert frontend_dict["changelog"] == []

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

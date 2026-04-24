"""Tests for scripts.bump_version."""

from __future__ import annotations

from datetime import date

import pytest

from scripts.bump_version import compute_next_version


class TestComputeNextVersion:
    def test_same_day_increments_build(self):
        result = compute_next_version(
            current="26.424.1", today=date(2026, 4, 24), explicit_build=None
        )
        assert result == "26.424.2"

    def test_same_day_increments_from_higher_build(self):
        result = compute_next_version(
            current="26.424.9", today=date(2026, 4, 24), explicit_build=None
        )
        assert result == "26.424.10"

    def test_new_day_resets_build_to_one(self):
        result = compute_next_version(
            current="26.424.5", today=date(2026, 4, 25), explicit_build=None
        )
        assert result == "26.425.1"

    def test_pre_migration_current_version_triggers_fresh_build(self):
        result = compute_next_version(
            current="1.8.4", today=date(2026, 4, 24), explicit_build=None
        )
        assert result == "26.424.1"

    def test_explicit_build_overrides(self):
        result = compute_next_version(
            current="26.424.1", today=date(2026, 4, 24), explicit_build=7
        )
        assert result == "26.424.7"

    def test_explicit_build_on_new_day_uses_today(self):
        result = compute_next_version(
            current="26.424.5", today=date(2026, 4, 25), explicit_build=3
        )
        assert result == "26.425.3"

    def test_day_with_leading_zero(self):
        result = compute_next_version(
            current="1.8.4", today=date(2026, 4, 4), explicit_build=None
        )
        assert result == "26.404.1"

    def test_october_day(self):
        result = compute_next_version(
            current="1.8.4", today=date(2026, 10, 4), explicit_build=None
        )
        assert result == "26.1004.1"

    def test_december_last_day(self):
        result = compute_next_version(
            current="1.8.4", today=date(2026, 12, 31), explicit_build=None
        )
        assert result == "26.1231.1"

    def test_january_first(self):
        result = compute_next_version(
            current="26.1231.5", today=date(2027, 1, 1), explicit_build=None
        )
        assert result == "27.101.1"

    def test_explicit_build_zero_rejected(self):
        with pytest.raises(ValueError, match="build.*must be.*>=.*1"):
            compute_next_version(
                current="26.424.1", today=date(2026, 4, 24), explicit_build=0
            )

    def test_explicit_build_negative_rejected(self):
        with pytest.raises(ValueError, match="build.*must be.*>=.*1"):
            compute_next_version(
                current="26.424.1", today=date(2026, 4, 24), explicit_build=-1
            )


from pathlib import Path

from scripts.bump_version import read_version_from_pyproject


class TestReadVersionFromPyproject:
    def test_reads_simple_version(self, tmp_path: Path):
        p = tmp_path / "pyproject.toml"
        p.write_text(
            '[project]\n'
            'name = "langflow"\n'
            'version = "1.8.4"\n'
            'description = "Foo"\n'
        )
        assert read_version_from_pyproject(p) == "1.8.4"

    def test_reads_calver(self, tmp_path: Path):
        p = tmp_path / "pyproject.toml"
        p.write_text('[project]\nname = "x"\nversion = "26.424.3"\n')
        assert read_version_from_pyproject(p) == "26.424.3"

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            read_version_from_pyproject(tmp_path / "does_not_exist.toml")

    def test_missing_version_raises(self, tmp_path: Path):
        p = tmp_path / "pyproject.toml"
        p.write_text('[project]\nname = "x"\n')
        with pytest.raises(ValueError, match="no.*version.*field"):
            read_version_from_pyproject(p)


from scripts.bump_version import write_version_to_pyproject


class TestWriteVersionToPyproject:
    def test_replaces_only_version_line(self, tmp_path: Path):
        p = tmp_path / "pyproject.toml"
        original = (
            "[project]\n"
            'name = "langflow"\n'
            'version = "1.8.4"\n'
            'description = "A flow builder"\n'
        )
        p.write_text(original)
        write_version_to_pyproject(p, "26.424.1")
        assert p.read_text() == (
            "[project]\n"
            'name = "langflow"\n'
            'version = "26.424.1"\n'
            'description = "A flow builder"\n'
        )

    def test_preserves_comments_and_blank_lines(self, tmp_path: Path):
        p = tmp_path / "pyproject.toml"
        original = (
            "# top comment\n"
            "\n"
            "[project]\n"
            'name = "x"\n'
            "# leading comment\n"
            'version = "0.3.4"  # trailing comment\n'
            "\n"
            "[tool.ruff]\n"
        )
        p.write_text(original)
        write_version_to_pyproject(p, "26.424.1")
        expected = (
            "# top comment\n"
            "\n"
            "[project]\n"
            'name = "x"\n'
            "# leading comment\n"
            'version = "26.424.1"  # trailing comment\n'
            "\n"
            "[tool.ruff]\n"
        )
        assert p.read_text() == expected

    def test_only_replaces_first_version_line(self, tmp_path: Path):
        p = tmp_path / "pyproject.toml"
        original = (
            "[project]\n"
            'name = "x"\n'
            'version = "1.0.0"\n'
            "[some.other.tool]\n"
            'version = "9.9.9"\n'
        )
        p.write_text(original)
        write_version_to_pyproject(p, "26.424.1")
        expected = (
            "[project]\n"
            'name = "x"\n'
            'version = "26.424.1"\n'
            "[some.other.tool]\n"
            'version = "9.9.9"\n'
        )
        assert p.read_text() == expected

    def test_missing_version_line_raises(self, tmp_path: Path):
        p = tmp_path / "pyproject.toml"
        p.write_text('[project]\nname = "x"\n')
        with pytest.raises(ValueError, match="no.*version.*line"):
            write_version_to_pyproject(p, "26.424.1")


from scripts.bump_version import write_version_to_package_json


class TestWriteVersionToPackageJson:
    def test_replaces_only_version_line(self, tmp_path: Path):
        p = tmp_path / "package.json"
        original = (
            "{\n"
            '  "name": "langflow",\n'
            '  "version": "1.8.4",\n'
            '  "private": true\n'
            "}\n"
        )
        p.write_text(original)
        write_version_to_package_json(p, "26.424.1")
        assert p.read_text() == (
            "{\n"
            '  "name": "langflow",\n'
            '  "version": "26.424.1",\n'
            '  "private": true\n'
            "}\n"
        )

    def test_preserves_indentation(self, tmp_path: Path):
        p = tmp_path / "package.json"
        p.write_text('{\n    "version": "0.0.1"\n}\n')
        write_version_to_package_json(p, "26.424.1")
        assert p.read_text() == '{\n    "version": "26.424.1"\n}\n'

    def test_missing_version_raises(self, tmp_path: Path):
        p = tmp_path / "package.json"
        p.write_text('{\n  "name": "x"\n}\n')
        with pytest.raises(ValueError, match="no.*version.*field"):
            write_version_to_package_json(p, "26.424.1")


import json
import subprocess
import sys
from textwrap import dedent


def _make_repo(tmp_path: Path) -> Path:
    """Create a minimal fake repo layout with all 4 version files at 1.8.4."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "langflow"\nversion = "1.8.4"\n'
    )
    nested = tmp_path / "src" / "backend" / "base"
    nested.mkdir(parents=True)
    (nested / "pyproject.toml").write_text(
        '[project]\nname = "langflow-base"\nversion = "0.8.4"\n'
    )
    lfx = tmp_path / "src" / "lfx"
    lfx.mkdir(parents=True)
    (lfx / "pyproject.toml").write_text(
        '[project]\nname = "lfx"\nversion = "0.3.4"\n'
    )
    fe = tmp_path / "src" / "frontend"
    fe.mkdir(parents=True)
    (fe / "package.json").write_text(
        '{\n  "name": "langflow",\n  "version": "1.8.4"\n}\n'
    )
    return tmp_path


class TestMainCLI:
    def test_writes_all_four_files_with_same_version(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        repo = _make_repo(tmp_path)
        monkeypatch.chdir(repo)
        monkeypatch.setenv("BUMP_VERSION_TODAY", "2026-04-24")

        from scripts.bump_version import main

        exit_code = main(["--build", "1"])
        assert exit_code == 0

        from scripts.bump_version import read_version_from_pyproject

        assert read_version_from_pyproject(repo / "pyproject.toml") == "26.424.1"
        assert (
            read_version_from_pyproject(repo / "src/backend/base/pyproject.toml")
            == "26.424.1"
        )
        assert read_version_from_pyproject(repo / "src/lfx/pyproject.toml") == "26.424.1"
        pkg = json.loads((repo / "src/frontend/package.json").read_text())
        assert pkg["version"] == "26.424.1"

    def test_check_mode_writes_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        repo = _make_repo(tmp_path)
        monkeypatch.chdir(repo)
        monkeypatch.setenv("BUMP_VERSION_TODAY", "2026-04-24")

        before = {
            f: (repo / f).read_text()
            for f in [
                "pyproject.toml",
                "src/backend/base/pyproject.toml",
                "src/lfx/pyproject.toml",
                "src/frontend/package.json",
            ]
        }

        from scripts.bump_version import main

        exit_code = main(["--check"])
        assert exit_code == 0

        after = {f: (repo / f).read_text() for f in before}
        assert before == after, "--check must not modify any files"

    def test_prints_new_version_to_stdout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        repo = _make_repo(tmp_path)
        monkeypatch.chdir(repo)
        monkeypatch.setenv("BUMP_VERSION_TODAY", "2026-04-24")

        from scripts.bump_version import main

        main(["--build", "3"])
        captured = capsys.readouterr()
        assert captured.out.strip() == "26.424.3"

    def test_missing_file_exits_nonzero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BUMP_VERSION_TODAY", "2026-04-24")

        from scripts.bump_version import main

        exit_code = main([])
        assert exit_code != 0

    def test_reject_zero_build(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        repo = _make_repo(tmp_path)
        monkeypatch.chdir(repo)
        monkeypatch.setenv("BUMP_VERSION_TODAY", "2026-04-24")

        from scripts.bump_version import main

        exit_code = main(["--build", "0"])
        assert exit_code != 0

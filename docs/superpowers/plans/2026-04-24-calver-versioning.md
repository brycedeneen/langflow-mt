# CalVer Versioning — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the four versioned packages in this repo (langflow, langflow-base, lfx, frontend) to a shared CalVer format `YY.{M}{DD}.{B}` starting at `26.424.1`, and add a repo-level Python script (`scripts/bump_version.py`) that computes and writes the next version across all four files in one command.

**Architecture:** A pure `compute_next_version(current, today, explicit_build)` function drives all version logic. Two thin I/O helpers (`read_version_from_pyproject`, `write_version_to_file`) use line-level regex to edit `version = "…"` and `"version": "…"` lines in place, preserving formatting and comments. A `main()` wires argparse + orchestration. Tests TDD the pure function exhaustively and verify the writers against tmp-dir fixtures. Initial migration is a separate, verifiable task performed once.

**Tech Stack:** Python 3.11+ (stdlib `tomllib`, `json`, `re`, `argparse`, `datetime`), pytest, GNU Make, npm.

**Branch:** work happens on the currently-checked-out branch (`platform-multi-tenant`, the effective main). No new branch or worktree.

**Source spec:** [`docs/superpowers/specs/2026-04-24-calver-versioning-design.md`](../specs/2026-04-24-calver-versioning-design.md)

**Commit policy:** Do **NOT** commit anything during execution. The user's standing preference is to review the full diff and commit/push manually at the end. A final handoff step surfaces the diff for review.

**Failure protocol:** If any test fails unexpectedly, any migration-time `uv sync` or `npm install` fails, or any step produces output that doesn't match "Expected", stop, report, and wait for direction before proceeding.

---

## File Structure

| Path | Responsibility | Created/Modified |
|---|---|---|
| `scripts/bump_version.py` | Version computation + file rewrites + CLI entry point. Single file, ~150 lines. | **Create** |
| `scripts/tests/__init__.py` | Makes `scripts/tests` a pytest-discoverable package. Empty file. | **Create** |
| `scripts/tests/test_bump_version.py` | Unit tests for `compute_next_version` and the file writers. | **Create** |
| `Makefile` | Add `bump-version` phony target. | **Modify** |
| `pyproject.toml` | `version` + `langflow-base[complete]` dep pin. | **Modify** |
| `src/backend/base/pyproject.toml` | `version` + `lfx` dep pin. | **Modify** |
| `src/lfx/pyproject.toml` | `version`. | **Modify** |
| `src/frontend/package.json` | `version`. | **Modify** |

---

## Task 1: Test scaffolding + `compute_next_version`

TDD the pure function that does all the version-computation logic.

**Files:**
- Create: `scripts/tests/__init__.py` (empty)
- Create: `scripts/tests/test_bump_version.py`
- Create: `scripts/bump_version.py`

- [ ] **Step 1: Create `scripts/tests/__init__.py`**

Create an empty file at `scripts/tests/__init__.py`:
```
```

(Zero bytes. Just needs to exist for pytest discovery.)

- [ ] **Step 2: Create stub `scripts/bump_version.py`**

This stub lets the test file import from the module before we implement anything:

```python
"""Compute and apply CalVer version bumps across the monorepo.

See docs/superpowers/specs/2026-04-24-calver-versioning-design.md.
"""

from __future__ import annotations

from datetime import date


def compute_next_version(current: str, today: date, explicit_build: int | None) -> str:
    """Compute the next CalVer version string.

    Format: YY.{M}{DD}.{B}
    - YY: 2-digit year, no leading zero
    - M: month 1-12, no leading zero
    - DD: day 01-31, always 2 digits (leading zero required)
    - B: build 1, 2, 3, ..., no leading zero
    """
    raise NotImplementedError
```

- [ ] **Step 3: Write the failing test file**

Create `scripts/tests/test_bump_version.py` with every pure-function test case from the spec:

```python
"""Tests for scripts.bump_version."""

from __future__ import annotations

from datetime import date

import pytest

from scripts.bump_version import compute_next_version


class TestComputeNextVersion:
    def test_same_day_increments_build(self):
        # Current 26.424.1 on 2026-04-24 -> 26.424.2
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
        # Current 26.424.5, today is 2026-04-25 -> 26.425.1
        result = compute_next_version(
            current="26.424.5", today=date(2026, 4, 25), explicit_build=None
        )
        assert result == "26.425.1"

    def test_pre_migration_current_version_triggers_fresh_build(self):
        # Current 1.8.4 is not CalVer; treat as "not today" -> today's .1
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
        # April 4 2026 -> 26.404.1 (not 26.44.1)
        result = compute_next_version(
            current="1.8.4", today=date(2026, 4, 4), explicit_build=None
        )
        assert result == "26.404.1"

    def test_october_day(self):
        # Oct 4 2026 -> 26.1004.1
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
```

- [ ] **Step 4: Run tests to verify they fail**

Run from repo root:
```bash
cd /Users/brycedeneen/dev/langflow && uv run pytest scripts/tests/test_bump_version.py -v
```
Expected: all 12 tests fail with `NotImplementedError` or collection errors.

- [ ] **Step 5: Implement `compute_next_version`**

Replace the `raise NotImplementedError` in `scripts/bump_version.py` with:

```python
"""Compute and apply CalVer version bumps across the monorepo.

See docs/superpowers/specs/2026-04-24-calver-versioning-design.md.
"""

from __future__ import annotations

import re
from datetime import date

_CALVER_RE = re.compile(r"^(\d{1,2})\.(\d{3,4})\.(\d+)$")


def _today_prefix(today: date) -> tuple[int, int]:
    """Return (yy, mdd) for today, where mdd is month*100 + day."""
    yy = today.year % 100
    mdd = today.month * 100 + today.day
    return yy, mdd


def compute_next_version(current: str, today: date, explicit_build: int | None) -> str:
    """Compute the next CalVer version string.

    Format: YY.{M}{DD}.{B}
    - YY: 2-digit year, no leading zero
    - M: month 1-12, no leading zero
    - DD: day 01-31, always 2 digits (leading zero required in the middle segment)
    - B: build 1, 2, 3, ..., no leading zero
    """
    if explicit_build is not None and explicit_build < 1:
        raise ValueError("build number must be >= 1")

    yy, mdd = _today_prefix(today)

    if explicit_build is not None:
        return f"{yy}.{mdd}.{explicit_build}"

    match = _CALVER_RE.match(current)
    if match and int(match.group(1)) == yy and int(match.group(2)) == mdd:
        next_build = int(match.group(3)) + 1
        return f"{yy}.{mdd}.{next_build}"

    return f"{yy}.{mdd}.1"
```

- [ ] **Step 6: Run tests to verify they pass**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && uv run pytest scripts/tests/test_bump_version.py -v
```
Expected: all 12 tests pass.

**Do NOT commit. Continue to Task 2.**

---

## Task 2: File I/O helpers

TDD three I/O functions: read version from a TOML file, write version to a TOML file, write version to a JSON file. All use line-level regex to preserve formatting.

**Files:**
- Modify: `scripts/bump_version.py` (add functions)
- Modify: `scripts/tests/test_bump_version.py` (add test classes)

- [ ] **Step 1: Add failing tests for `read_version_from_pyproject`**

Append to `scripts/tests/test_bump_version.py`:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && uv run pytest scripts/tests/test_bump_version.py::TestReadVersionFromPyproject -v
```
Expected: 4 tests fail with ImportError (no such name).

- [ ] **Step 3: Implement `read_version_from_pyproject`**

Add to `scripts/bump_version.py` (after the existing code):

```python
import tomllib
from pathlib import Path


def read_version_from_pyproject(path: Path) -> str:
    """Read `[project].version` from a pyproject.toml."""
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("rb") as f:
        data = tomllib.load(f)
    try:
        return data["project"]["version"]
    except KeyError as exc:
        raise ValueError(f"{path}: no [project].version field") from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && uv run pytest scripts/tests/test_bump_version.py::TestReadVersionFromPyproject -v
```
Expected: 4 tests pass.

- [ ] **Step 5: Add failing tests for `write_version_to_pyproject`**

Append to `scripts/tests/test_bump_version.py`:

```python
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
        # A dependency constraint might also mention "version = " but we only
        # want to touch the project's own version.
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
```

- [ ] **Step 6: Run to verify they fail**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && uv run pytest scripts/tests/test_bump_version.py::TestWriteVersionToPyproject -v
```
Expected: 4 tests fail.

- [ ] **Step 7: Implement `write_version_to_pyproject`**

Add to `scripts/bump_version.py`:

```python
_PYPROJECT_VERSION_RE = re.compile(
    r'^(?P<prefix>version\s*=\s*")[^"]*(?P<suffix>".*)$',
    re.MULTILINE,
)


def write_version_to_pyproject(path: Path, new_version: str) -> None:
    """Replace the first `version = "…"` line in a pyproject.toml.

    Uses line-level regex to preserve comments, blank lines, and formatting.
    Only replaces the FIRST match (which is always [project].version in our files).
    """
    content = path.read_text()
    new_content, count = _PYPROJECT_VERSION_RE.subn(
        lambda m: f'{m.group("prefix")}{new_version}{m.group("suffix")}',
        content,
        count=1,
    )
    if count == 0:
        raise ValueError(f"{path}: no `version = \"...\"` line found")
    path.write_text(new_content)
```

- [ ] **Step 8: Run tests to verify they pass**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && uv run pytest scripts/tests/test_bump_version.py::TestWriteVersionToPyproject -v
```
Expected: 4 tests pass.

- [ ] **Step 9: Add failing tests for `write_version_to_package_json`**

Append to `scripts/tests/test_bump_version.py`:

```python
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
```

- [ ] **Step 10: Run to verify they fail**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && uv run pytest scripts/tests/test_bump_version.py::TestWriteVersionToPackageJson -v
```
Expected: 3 tests fail.

- [ ] **Step 11: Implement `write_version_to_package_json`**

Add to `scripts/bump_version.py`:

```python
_PACKAGE_JSON_VERSION_RE = re.compile(
    r'(?P<prefix>"version"\s*:\s*")[^"]*(?P<suffix>")',
)


def write_version_to_package_json(path: Path, new_version: str) -> None:
    """Replace the first `"version": "…"` in a package.json.

    Uses line-level regex to preserve exact formatting (indentation, key order).
    """
    content = path.read_text()
    new_content, count = _PACKAGE_JSON_VERSION_RE.subn(
        lambda m: f'{m.group("prefix")}{new_version}{m.group("suffix")}',
        content,
        count=1,
    )
    if count == 0:
        raise ValueError(f'{path}: no `"version": "..."` field found')
    path.write_text(new_content)
```

- [ ] **Step 12: Run tests to verify they pass**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && uv run pytest scripts/tests/test_bump_version.py -v
```
Expected: all tests so far (12 compute + 4 read + 4 write pyproject + 3 write package.json = 23) pass.

**Do NOT commit. Continue to Task 3.**

---

## Task 3: CLI `main()` with argparse

Wire up the script as an executable CLI. Supports `--build N`, `--check`, and prints the new version to stdout.

**Files:**
- Modify: `scripts/bump_version.py` (add `main`, file list, `__main__` block)
- Modify: `scripts/tests/test_bump_version.py` (add CLI tests)

- [ ] **Step 1: Add the TARGET_FILES constant**

Append to `scripts/bump_version.py`, after the I/O helpers:

```python
# Files the CLI operates on, relative to the repo root.
# Order matters for --check output: pyproject first (source of truth), then the rest.
TARGET_FILES: tuple[tuple[str, str], ...] = (
    ("pyproject.toml", "toml"),
    ("src/backend/base/pyproject.toml", "toml"),
    ("src/lfx/pyproject.toml", "toml"),
    ("src/frontend/package.json", "json"),
)
```

- [ ] **Step 2: Add failing tests for CLI behavior**

Append to `scripts/tests/test_bump_version.py`:

```python
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
        # freeze today via env var we'll honor in main() for testability
        monkeypatch.setenv("BUMP_VERSION_TODAY", "2026-04-24")

        from scripts.bump_version import main

        exit_code = main(["--build", "1"])
        assert exit_code == 0

        # all four files should now read 26.424.1
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

        after = {
            f: (repo / f).read_text()
            for f in before
        }
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
        # Don't create any files. Running in this empty dir should fail cleanly.
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
```

- [ ] **Step 3: Run to verify they fail**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && uv run pytest scripts/tests/test_bump_version.py::TestMainCLI -v
```
Expected: 5 tests fail (no such name `main`).

- [ ] **Step 4: Implement `main()`**

Append to `scripts/bump_version.py`:

```python
import argparse
import os
import sys
from datetime import date


def _resolve_today() -> date:
    """Allow overriding 'today' via env var for test determinism."""
    override = os.environ.get("BUMP_VERSION_TODAY")
    if override:
        return date.fromisoformat(override)
    return date.today()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bump all four package versions to a new CalVer string."
    )
    parser.add_argument(
        "--build",
        type=int,
        default=None,
        help="Explicit build number (>=1). Default: auto-increment same-day, "
        "else reset to 1.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Dry-run: print what would change, write nothing.",
    )
    args = parser.parse_args(argv)

    today = _resolve_today()

    # Source of truth for current version: root pyproject.toml
    root_pyproject = Path("pyproject.toml")
    try:
        current = read_version_from_pyproject(root_pyproject)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: cannot read current version: {exc}", file=sys.stderr)
        return 2

    try:
        new_version = compute_next_version(current, today, args.build)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.check:
        print(f"Would bump: {current} -> {new_version}", file=sys.stderr)
        for rel, _kind in TARGET_FILES:
            print(f"  {rel}", file=sys.stderr)
        print(new_version)
        return 0

    # Apply to all files
    for rel, kind in TARGET_FILES:
        path = Path(rel)
        try:
            if kind == "toml":
                write_version_to_pyproject(path, new_version)
            elif kind == "json":
                write_version_to_package_json(path, new_version)
            else:
                raise ValueError(f"unknown file kind: {kind}")
        except (FileNotFoundError, ValueError) as exc:
            print(f"error: writing {path}: {exc}", file=sys.stderr)
            return 2

    print(new_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && uv run pytest scripts/tests/test_bump_version.py -v
```
Expected: all tests pass (23 from earlier tasks + 5 CLI tests = 28 total).

- [ ] **Step 6: Sanity-check the script against the real repo (dry run)**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && uv run python scripts/bump_version.py --check
```
Expected:
- stderr lines listing the 4 files and a "Would bump: 1.8.4 -> 26.424.1" summary
- stdout: `26.424.1`
- exit 0
- no files modified (verify with `git status --porcelain pyproject.toml src/backend/base/pyproject.toml src/lfx/pyproject.toml src/frontend/package.json`)

If the script reports anything other than `26.424.1` (e.g., the date has rolled over since this plan was written), use that date's value everywhere it's mentioned in later tasks.

**Do NOT commit. Continue to Task 4.**

---

## Task 4: Makefile target

Add `bump-version` and `bump-version-check` targets to the existing `Makefile`.

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Find the right place to insert**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && grep -n "^.PHONY:" Makefile | head -1
```
Expected: one line starting with `.PHONY:` listing all phony targets.

- [ ] **Step 2: Add `bump-version` and `bump-version-check` to `.PHONY`**

Edit the first line of `Makefile`. Currently:
```
.PHONY: all init format_backend format lint build run_backend dev help tests coverage clean_python_cache clean_npm_cache clean_frontend_build clean_all run_clic load_test_setup load_test_setup_basic load_test_list_flows load_test_run load_test_langflow_quick load_test_stress load_test_example load_test_clean load_test_remote_setup load_test_remote_run load_test_help docs docs_build docs_install
```

Append ` bump-version bump-version-check` to that line (after `docs_install`).

- [ ] **Step 3: Append the target definitions at the end of the Makefile**

Append to the end of `Makefile`:

```makefile

######################
# VERSIONING
######################

bump-version: ## compute and write the next CalVer version across all 4 packages
	@uv run python scripts/bump_version.py

bump-version-check: ## dry-run: show what bump-version would change
	@uv run python scripts/bump_version.py --check
```

- [ ] **Step 4: Verify the target works**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && make bump-version-check
```
Expected: same output as Task 3 Step 6 (`26.424.1` on stdout, file list on stderr, exit 0).

- [ ] **Step 5: Sanity-check `make help` still works**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && make help | grep -E "bump-version" | head -5
```
Expected: two lines showing the new `bump-version` and `bump-version-check` targets with their descriptions.

If `make help` relies on a specific comment format that we didn't match, adjust the comment style to whatever is used by neighboring targets — do not invent a new format.

**Do NOT commit. Continue to Task 5.**

---

## Task 5: Initial migration (edit the 6 fields)

Use the script to bump versions, then hand-edit the two inter-package dep pins which the script intentionally does not touch.

**Files:**
- Modify: `pyproject.toml` (version + dep pin)
- Modify: `src/backend/base/pyproject.toml` (version + dep pin)
- Modify: `src/lfx/pyproject.toml` (version)
- Modify: `src/frontend/package.json` (version)

- [ ] **Step 1: Run the bump script**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && uv run python scripts/bump_version.py --build 1
```
Expected: stdout prints `26.424.1`. Exit 0.

- [ ] **Step 2: Verify all 4 files are at the new version**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && grep '^version' pyproject.toml src/backend/base/pyproject.toml src/lfx/pyproject.toml && grep '"version"' src/frontend/package.json
```
Expected output:
```
pyproject.toml:version = "26.424.1"
src/backend/base/pyproject.toml:version = "26.424.1"
src/lfx/pyproject.toml:version = "26.424.1"
  "version": "26.424.1",
```

- [ ] **Step 3: Update the `langflow-base` dep pin in root `pyproject.toml`**

Edit `pyproject.toml`. Change line 20:
```
    "langflow-base[complete]~=0.8.4",
```
to:
```
    "langflow-base[complete]>=26.424.1",
```

- [ ] **Step 4: Update the `lfx` dep pin in `src/backend/base/pyproject.toml`**

Edit `src/backend/base/pyproject.toml`. Change line 20:
```
    "lfx~=0.3.4",
```
to:
```
    "lfx>=26.424.1",
```

- [ ] **Step 5: Confirm no other `~=0.X.Y` pins against these three packages**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && grep -nE '(langflow|langflow-base|lfx)\s*~=' pyproject.toml src/backend/base/pyproject.toml src/lfx/pyproject.toml
```
Expected: no output.

If any matches remain, update them to `>=26.424.1` following the same pattern as Steps 3–4. Stop and report which file(s).

- [ ] **Step 6: Run `uv sync` to verify Python dep resolution**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && uv sync 2>&1 | tail -20
```
Expected: exit 0, no "failed to resolve" errors. The workspace packages re-resolve to `26.424.1`.

If `uv sync` fails with a dep-resolution error mentioning `langflow`, `langflow-base`, or `lfx`, STOP — there's a pin somewhere that Step 5's grep didn't catch.

- [ ] **Step 7: Run `npm install` in the frontend to verify semver**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npm install 2>&1 | tail -10
```
Expected: exit 0, no "Invalid version" errors.

If npm complains about the version format, STOP and report — semantics of `26.424.1` should be valid but something external may differ.

- [ ] **Step 8: Confirm runtime version reads correctly**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && uv run python -c "from importlib.metadata import version; print(version('langflow'))"
```
Expected: `26.424.1`.

If this prints the old `1.8.4`, the editable install didn't pick up the metadata change — re-run `uv sync` or `uv pip install -e .` and try again.

- [ ] **Step 9: Confirm the Makefile version extraction still works**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && make -n docker_build 2>&1 | head -3 ; echo "---"; grep 'VERSION=' Makefile | head -2
```
Expected: `make` continues to resolve `VERSION` to `26.424.1` via its inline `grep | sed`. If you see `1.8.4` still, the caching isn't the issue — `make` re-reads on every invocation, so the shell/grep must be finding the updated line.

You can verify directly:
```bash
cd /Users/brycedeneen/dev/langflow && grep "^version" pyproject.toml | sed 's/.*\"\(.*\)\"$/\1/'
```
Expected: `26.424.1`.

**Do NOT commit. Continue to Task 6.**

---

## Task 6: End-to-end sanity check

Confirm the installed script, when run a second time on the same day, proposes the next build number.

**Files:** none modified.

- [ ] **Step 1: Dry-run `bump-version-check` after migration**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && make bump-version-check
```
Expected: stdout `26.424.2` (build incremented), stderr "Would bump: 26.424.1 -> 26.424.2", exit 0, no files modified.

Verify nothing changed:
```bash
cd /Users/brycedeneen/dev/langflow && git status --porcelain pyproject.toml src/backend/base/pyproject.toml src/lfx/pyproject.toml src/frontend/package.json | head
```
(Expected output: the two pyproject.toml files and both package files should still appear modified from the migration — but no additional new modifications from the check run. The key is that `git diff --stat` after this check produces no additional changes relative to the previous step.)

- [ ] **Step 2: Show the final cumulative diff**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && git diff --stat pyproject.toml src/backend/base/pyproject.toml src/lfx/pyproject.toml src/frontend/package.json && echo "---" && git status --porcelain scripts Makefile | head -20
```
Expected:
- `--stat` shows 4 files modified (the versions + 2 dep pins)
- `git status --porcelain` shows:
  - `M  Makefile` (bump-version targets added)
  - `?? scripts/bump_version.py` (new)
  - `?? scripts/tests/__init__.py` (new)
  - `?? scripts/tests/test_bump_version.py` (new)

- [ ] **Step 3: Final summary report**

Produce the final summary:

```
CalVer migration — summary

Version change:  1.8.4 (langflow) / 0.8.4 (base) / 0.3.4 (lfx) / 1.8.4 (frontend)
                 -> 26.424.1 for all 4

Dep pins:        langflow-base[complete]~=0.8.4 -> >=26.424.1
                 lfx~=0.3.4                       -> >=26.424.1

New tooling:     scripts/bump_version.py
                 scripts/tests/test_bump_version.py (28 tests passing)
                 Makefile targets: bump-version, bump-version-check

Verification:    uv sync                      ✓
                 npm install (frontend)        ✓
                 importlib.metadata.version    ✓ (reads 26.424.1)
                 make bump-version-check       ✓ (proposes 26.424.2)

Uncommitted. Ready for user review + commit + push.
```

- [ ] **Step 4: Hand off to user**

Say, verbatim or close to it:

> "CalVer migration complete and verified. 6 files modified + 3 new script/test files. Nothing committed. Let me know when you want to stage and commit, and I'll draft the message for your approval."

Do NOT stage, commit, or push. Per project memory, `git commit` requires explicit user permission.

---

## Self-review notes

Spec coverage check:
- Format rules (YY, M, DD, B) ✓ (Task 1 compute_next_version + tests)
- Four version files listed ✓ (Task 3 TARGET_FILES, Task 5 migration)
- Two inter-package pins updated ✓ (Task 5 Steps 3–4)
- Helper script with `--check`, `--build N` ✓ (Task 3)
- Makefile target ✓ (Task 4)
- All 10 spec test cases ✓ (Task 1 has 12 — covers the 10 plus two build-validation cases)
- Unit tests for I/O helpers ✓ (Task 2)
- Verification commands (`uv sync`, `npm install`, `importlib.metadata.version`, `bump_version.py --check`) ✓ (Task 5 Steps 6–8, Task 6 Step 1)
- No commits during execution ✓ (every task ends with "Do NOT commit")
- Script does NOT touch inter-package pins ongoing ✓ (Task 3 TARGET_FILES omits them)
- Script does NOT commit ✓ (no git ops in main())

Placeholder scan: clean — no TBD/TODO/"similar to X" markers; every code block is complete.

Type consistency: `compute_next_version`, `read_version_from_pyproject`, `write_version_to_pyproject`, `write_version_to_package_json`, `main`, `TARGET_FILES` — names match across all tasks and test imports.

---

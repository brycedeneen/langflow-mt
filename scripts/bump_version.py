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


# Files the CLI operates on, relative to the repo root.
# Order matters for --check output: pyproject first (source of truth), then the rest.
TARGET_FILES: tuple[tuple[str, str], ...] = (
    ("pyproject.toml", "toml"),
    ("src/backend/base/pyproject.toml", "toml"),
    ("src/lfx/pyproject.toml", "toml"),
    ("src/frontend/package.json", "json"),
)


import argparse
import os
import sys


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

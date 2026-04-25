"""Emit per-category YAML bundles and a markdown review report."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

import yaml as _yaml

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class GuideEntry:
    category: str
    component_name: str
    agent_summary: str
    agent_usage_notes: str


@dataclass(frozen=True)
class ReportRow:
    component_name: str
    category: str
    # Expected values: "rich", "thin"
    metadata_completeness: str
    # Expected values: "processed", "skipped-opted-out", "skipped-legacy",
    # "skipped-existing", "errored"
    outcome: str
    # Expected values: "generated", "fallback-used", "errored", "n/a"
    summary_status: str
    # Expected values: "generated", "fallback-used", "errored", "n/a"
    usage_status: str


class _LiteralStr(str):
    """A str subclass rendered with literal block scalar (`|`) for readability."""

    __slots__ = ()


def _literal_presenter(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style="|")


_yaml.add_representer(_LiteralStr, _literal_presenter)


def write_bundle(entries: list[GuideEntry], out_dir: Path, *, overwrite: bool) -> None:
    """Write per-category YAML files. Entries within each file are sorted by component_name.

    When ``overwrite=False``, existing entries with a matching ``component_name`` are
    preserved verbatim (read from the file on disk before merging in new entries).
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    grouped: dict[str, list[GuideEntry]] = defaultdict(list)
    for e in entries:
        grouped[e.category].append(e)

    for category, new_entries in grouped.items():
        path = out_dir / f"{category}.yaml"
        existing_by_name: dict[str, dict] = {}
        if path.exists():
            try:
                raw = _yaml.safe_load(path.read_text()) or []
                if isinstance(raw, list):
                    for entry in raw:
                        if isinstance(entry, dict) and "component_name" in entry:
                            existing_by_name[entry["component_name"]] = entry
            except _yaml.YAMLError:
                # Malformed file - we'll overwrite it.
                existing_by_name = {}

        merged: dict[str, dict] = dict(existing_by_name)
        for e in new_entries:
            if e.component_name in existing_by_name and not overwrite:
                continue
            merged[e.component_name] = {
                "component_name": e.component_name,
                "agent_summary": _LiteralStr(e.agent_summary),
                "agent_usage_notes": _LiteralStr(e.agent_usage_notes),
            }

        ordered = sorted(merged.values(), key=lambda d: d["component_name"])
        path.write_text(
            _yaml.dump(
                ordered,
                sort_keys=False,
                allow_unicode=True,
                default_flow_style=False,
            )
        )


def write_review_report(rows: list[ReportRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Component Agent Metadata Generation Report\n\n"
        "| Component | Category | Completeness | Outcome | Summary Status | Usage Status |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
    )
    body_lines = [
        (
            f"| {r.component_name} | {r.category} | {r.metadata_completeness} | "
            f"{r.outcome} | {r.summary_status} | {r.usage_status} |"
        )
        for r in sorted(rows, key=lambda x: (x.category, x.component_name))
    ]
    path.write_text(header + "\n".join(body_lines) + "\n")

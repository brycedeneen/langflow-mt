"""YAML bundle writer + review report generator."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

import yaml


@dataclass(frozen=True)
class GuideEntry:
    category: str
    component_type: str
    guide: str


@dataclass(frozen=True)
class ReportRow:
    component_type: str
    category: str
    completeness: Literal["rich", "thin"]
    status: Literal[
        "generated",
        "skipped-existing",
        "skipped-opted-out",
        "fallback-used",
        "errored",
    ]


def _load_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text()) or []
    return raw if isinstance(raw, list) else []


def write_bundle(entries: Iterable[GuideEntry], out_dir: Path, *, overwrite: bool = False) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    by_category: dict[str, list[GuideEntry]] = {}
    for entry in entries:
        by_category.setdefault(entry.category, []).append(entry)

    for category, new_entries in sorted(by_category.items()):
        path = out_dir / f"{category}.yaml"
        existing = _load_existing(path)
        existing_types = {e.get("type") for e in existing}

        merged = list(existing)
        for entry in new_entries:
            if entry.component_type in existing_types and not overwrite:
                continue
            merged = [e for e in merged if e.get("type") != entry.component_type]
            merged.append({"type": entry.component_type, "guide": entry.guide})

        merged.sort(key=lambda e: e["type"])
        path.write_text(yaml.safe_dump(merged, sort_keys=False, allow_unicode=True, width=100))


def write_review_report(rows: Iterable[ReportRow], path: Path) -> None:
    rows_list = list(rows)
    thin = [r for r in rows_list if r.completeness == "thin"]
    opted_out = [r for r in rows_list if r.status == "skipped-opted-out"]
    lines: list[str] = [
        "# Component Assist Guide — Review Report",
        "",
        f"Total components processed: {len(rows_list)}",
        f"Generated: {sum(1 for r in rows_list if r.status == 'generated')}",
        f"Fallback used: {sum(1 for r in rows_list if r.status == 'fallback-used')}",
        f"Skipped (existing): {sum(1 for r in rows_list if r.status == 'skipped-existing')}",
        f"Skipped (opted out): {len(opted_out)}",
        f"Errored: {sum(1 for r in rows_list if r.status == 'errored')}",
        "",
        "## Opted out of ADP Assist",
        "",
    ]
    if not opted_out:
        lines.append("_None._")
    else:
        for row in sorted(opted_out, key=lambda r: (r.category, r.component_type)):
            lines.append(f"- `{row.category}/` · **{row.component_type}**")
    lines.append("")
    lines.append("## Flagged for manual review (thin metadata)")
    lines.append("")
    if not thin:
        lines.append("_None — every component had sufficient metadata._")
    else:
        for row in sorted(thin, key=lambda r: (r.category, r.component_type)):
            lines.append(f"- `{row.category}/` · **{row.component_type}** — {row.status}")
    lines.append("")
    path.write_text("\n".join(lines))

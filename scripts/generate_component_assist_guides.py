#!/usr/bin/env python
"""Generate starter assist_guides for every user-facing Langflow component.

Run from repo root. See ``--help`` for flags.
"""
from __future__ import annotations

import argparse
import importlib.util
import inspect
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Ensure repo root is on sys.path so the sibling `scripts._assist_guide_gen` package resolves
# when this file is invoked as a script (`python scripts/generate_...`).
_REPO_ROOT_FOR_IMPORT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_FOR_IMPORT))

from scripts._assist_guide_gen.emit import (
    GuideEntry,
    ReportRow,
    write_bundle,
    write_review_report,
)
from scripts._assist_guide_gen.extract import (
    ComponentMetadata,
    extract_metadata,
    metadata_completeness,
)
from scripts._assist_guide_gen.synthesize import synthesize_guide
from scripts._assist_guide_gen.walker import FileCandidate, iter_all

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPONENT_ROOTS = (
    REPO_ROOT / "src/lfx/src/lfx/components",
    REPO_ROOT / "src/backend/base/langflow/components",
)
GUIDES_DIR = REPO_ROOT / "src/backend/base/langflow/services/component_assist/guides"
REPORT_PATH = REPO_ROOT / "docs/adp-assist-guide-generation-report.md"


def _find_component_classes(candidate: FileCandidate) -> list[type]:
    """Import the module at ``candidate.path`` and return all Component subclasses it defines."""
    module_name = f"_assist_guide_module_{candidate.path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, candidate.path)
    if spec is None or spec.loader is None:
        return []
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return []

    from lfx.custom.custom_component.component import Component  # local import; heavy

    out: list[type] = []
    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ != module.__name__:
            continue
        if not issubclass(obj, Component) or obj is Component:
            continue
        out.append(obj)
    return out


def _build_llm() -> "object":
    """Return a callable ``(prompt: str) -> str`` backed by the Anthropic SDK."""
    import anthropic

    client = anthropic.Anthropic()

    def call(prompt: str) -> str:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [block.text for block in resp.content if getattr(block, "type", "") == "text"]
        return "\n".join(parts).strip()

    return call


def _process_one(
    candidate: FileCandidate,
    existing_types: set[str],
    overwrite: bool,
    llm,
) -> tuple[list[GuideEntry], list[ReportRow]]:
    from langflow.services.component_assist.guide_registry import is_assist_enabled

    entries: list[GuideEntry] = []
    rows: list[ReportRow] = []
    for cls in _find_component_classes(candidate):
        class_name = cls.__name__
        if not is_assist_enabled(cls):
            rows.append(ReportRow(class_name, candidate.category, "rich", "skipped-opted-out"))
            continue
        if getattr(cls, "assist_guide", None):
            rows.append(ReportRow(class_name, candidate.category, "rich", "skipped-existing"))
            continue
        if class_name in existing_types and not overwrite:
            rows.append(ReportRow(class_name, candidate.category, "rich", "skipped-existing"))
            continue

        meta: ComponentMetadata = extract_metadata(cls)
        completeness = metadata_completeness(meta)
        try:
            guide = synthesize_guide(meta, llm=llm)
            status = "generated" if guide and guide.strip() else "fallback-used"
        except Exception as exc:  # noqa: BLE001
            guide = ""
            status = "errored"
            print(f"! {class_name}: {exc}", file=sys.stderr)
        if guide:
            entries.append(GuideEntry(candidate.category, class_name, guide))
        rows.append(ReportRow(class_name, candidate.category, completeness, status))
    return entries, rows


def _existing_bundle_types(out_dir: Path) -> set[str]:
    import yaml

    types: set[str] = set()
    for path in out_dir.glob("*.yaml"):
        raw = yaml.safe_load(path.read_text()) or []
        if isinstance(raw, list):
            types.update(e["type"] for e in raw if isinstance(e, dict) and "type" in e)
    return types


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ADP Assist component guides.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing guides.")
    parser.add_argument("--category", help="Restrict generation to one top-level category.")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()

    candidates = list(iter_all(COMPONENT_ROOTS))
    if args.category:
        candidates = [c for c in candidates if c.category == args.category]

    if args.dry_run:
        print(f"Would process {len(candidates)} files across {len({c.category for c in candidates})} categories.")
        return 0

    existing_types = _existing_bundle_types(GUIDES_DIR)
    llm = _build_llm()

    all_entries: list[GuideEntry] = []
    all_rows: list[ReportRow] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(_process_one, c, existing_types, args.overwrite, llm): c
            for c in candidates
        }
        for i, fut in enumerate(as_completed(futures), start=1):
            c = futures[fut]
            try:
                entries, rows = fut.result()
            except Exception as exc:
                print(f"!! {c.path}: {exc}", file=sys.stderr)
                if args.fail_fast:
                    return 1
                continue
            all_entries.extend(entries)
            all_rows.extend(rows)
            print(f"[{i}/{len(candidates)}] {c.category}/{c.path.name}")

    write_bundle(all_entries, GUIDES_DIR, overwrite=args.overwrite)
    write_review_report(all_rows, REPORT_PATH)
    print(f"\nWrote {len(all_entries)} guides to {GUIDES_DIR}")
    print(f"Review report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

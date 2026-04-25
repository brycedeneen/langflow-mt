#!/usr/bin/env python
"""Generate starter agent_summary + agent_usage_notes for assist-enabled components.

Generates per-class agent_summary + agent_usage_notes for every assist-enabled,
non-legacy Langflow component. Run from repo root. See ``--help`` for flags.
"""
from __future__ import annotations

import argparse
import importlib.util
import inspect
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Ensure repo root is on sys.path so the sibling `scripts._agent_metadata_gen` package resolves
# when this file is invoked as a script (`python scripts/generate_...`).
_REPO_ROOT_FOR_IMPORT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_FOR_IMPORT))

from scripts._agent_metadata_gen.emit import (  # noqa: E402
    GuideEntry,
    ReportRow,
    write_bundle,
    write_review_report,
)
from scripts._agent_metadata_gen.generate import decide_outcome  # noqa: E402
from scripts._agent_metadata_gen.peers import PeerEntry, build_peer_index  # noqa: E402
from scripts._agent_metadata_gen.synthesize import synthesize_pair  # noqa: E402
from scripts._assist_guide_gen.extract import extract_metadata, metadata_completeness  # noqa: E402
from scripts._assist_guide_gen.walker import FileCandidate, iter_all  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPONENT_ROOTS = (
    REPO_ROOT / "src/lfx/src/lfx/components",
    REPO_ROOT / "src/backend/base/langflow/components",
)
BUNDLE_DIR = REPO_ROOT / "src/backend/base/langflow/services/component_assist/agent_metadata"
REPORT_PATH = REPO_ROOT / "docs/component-agent-metadata-generation-report.md"


def _find_component_classes(candidate: FileCandidate) -> list[type]:
    module_name = f"_agent_metadata_module_{candidate.path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, candidate.path)
    if spec is None or spec.loader is None:
        return []
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001
        print(f"! import failed: {candidate.path}: {exc}", file=sys.stderr)
        return []

    from lfx.custom.custom_component.component import Component  # heavy import

    out: list[type] = []
    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ != module.__name__:
            continue
        if not issubclass(obj, Component) or obj is Component:
            continue
        out.append(obj)
    return out


def _build_llm():
    """Return a callable ``(prompt: str) -> str`` backed by the Anthropic SDK."""
    import anthropic

    client = anthropic.Anthropic()

    def call(prompt: str) -> str:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=900,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [block.text for block in resp.content if getattr(block, "type", "") == "text"]
        return "\n".join(parts).strip()

    return call


def _existing_bundle_types(bundle_dir: Path) -> set[str]:
    import yaml as _yaml

    types: set[str] = set()
    if not bundle_dir.is_dir():
        return types
    for path in bundle_dir.glob("*.yaml"):
        try:
            raw = _yaml.safe_load(path.read_text()) or []
        except _yaml.YAMLError as exc:
            print(f"! Skipping malformed bundle YAML {path.name}: {exc}", file=sys.stderr)
            continue
        if isinstance(raw, list):
            types.update(
                e["component_name"] for e in raw if isinstance(e, dict) and "component_name" in e
            )
    return types


def _scan_classes(candidates: list[FileCandidate]) -> list[tuple[type, str]]:
    """Discover all component classes across candidates. Returns (class, category) pairs."""
    out: list[tuple[type, str]] = []
    for candidate in candidates:
        out.extend((cls, candidate.category) for cls in _find_component_classes(candidate))
    return out


def _process_one_class(
    cls: type,
    category: str,
    *,
    existing_types: set[str],
    overwrite: bool,
    peers: list[PeerEntry],
    llm,
) -> tuple[GuideEntry | None, ReportRow]:
    outcome = decide_outcome(cls, existing_types=existing_types, overwrite=overwrite)
    if outcome != "processed":
        return None, ReportRow(
            component_name=cls.__name__,
            category=category,
            metadata_completeness="n/a",
            outcome=outcome,
            summary_status="n/a",
            usage_status="n/a",
        )

    meta = extract_metadata(cls)
    completeness = metadata_completeness(meta)
    try:
        summary, summary_status, notes, notes_status = synthesize_pair(
            meta, peers=peers, llm=llm,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"! {cls.__name__}: {exc}", file=sys.stderr)
        return None, ReportRow(
            component_name=cls.__name__,
            category=category,
            metadata_completeness=completeness,
            outcome="errored",
            summary_status="errored",
            usage_status="errored",
        )

    entry = GuideEntry(
        category=category,
        component_name=cls.__name__,
        agent_summary=summary,
        agent_usage_notes=notes,
    )
    row = ReportRow(
        component_name=cls.__name__,
        category=category,
        metadata_completeness=completeness,
        outcome="processed",
        summary_status=summary_status,
        usage_status=notes_status,
    )
    return entry, row


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate component agent_summary + agent_usage_notes.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing entries.")
    parser.add_argument("--category", help="Restrict generation to one top-level category.")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()

    candidates = list(iter_all(COMPONENT_ROOTS))
    if args.category:
        candidates = [c for c in candidates if c.category == args.category]

    if args.dry_run:
        print(
            f"Would process {len(candidates)} files across "
            f"{len({c.category for c in candidates})} categories."
        )
        return 0

    # Scan all classes across all candidates first so the peer index is complete.
    print(f"Scanning {len(candidates)} files for component classes...")
    classes = _scan_classes(candidates)
    print(f"Discovered {len(classes)} component classes.")

    peer_index = build_peer_index(classes)
    existing_types = _existing_bundle_types(BUNDLE_DIR)
    llm = _build_llm()

    all_entries: list[GuideEntry] = []
    all_rows: list[ReportRow] = []

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(
                _process_one_class,
                cls,
                category,
                existing_types=existing_types,
                overwrite=args.overwrite,
                peers=peer_index.get(category, []),
                llm=llm,
            ): (cls, category)
            for cls, category in classes
        }
        for i, fut in enumerate(as_completed(futures), start=1):
            cls, category = futures[fut]
            try:
                entry, row = fut.result()
            except Exception as exc:  # noqa: BLE001
                print(f"!! {cls.__name__} ({category}): {exc}", file=sys.stderr)
                if args.fail_fast:
                    return 1
                continue
            if entry is not None:
                all_entries.append(entry)
            all_rows.append(row)
            print(f"[{i}/{len(classes)}] {category}/{cls.__name__} -> {row.outcome}")
            if row.outcome == "errored" and args.fail_fast:
                print("Stopping early due to --fail-fast.", file=sys.stderr)
                return 1

    write_bundle(all_entries, BUNDLE_DIR, overwrite=args.overwrite)
    write_review_report(all_rows, REPORT_PATH)
    print(f"\nWrote {len(all_entries)} bundle entries to {BUNDLE_DIR}")
    print(f"Review report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

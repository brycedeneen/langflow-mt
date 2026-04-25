"""YAML emit + review report tests."""
from __future__ import annotations

from pathlib import Path

import yaml

from scripts._assist_guide_gen.emit import (
    GuideEntry,
    ReportRow,
    write_bundle,
    write_review_report,
)


def test_write_bundle_partitions_by_category(tmp_path: Path):
    entries = [
        GuideEntry(category="processing", component_type="AComponent", guide="A guide."),
        GuideEntry(category="processing", component_type="BComponent", guide="B guide."),
        GuideEntry(category="vectorstores", component_type="CComponent", guide="C guide."),
    ]
    write_bundle(entries, tmp_path)

    proc = yaml.safe_load((tmp_path / "processing.yaml").read_text())
    assert {e["type"] for e in proc} == {"AComponent", "BComponent"}

    vec = yaml.safe_load((tmp_path / "vectorstores.yaml").read_text())
    assert vec[0]["type"] == "CComponent"


def test_write_bundle_skips_existing_entries_by_default(tmp_path: Path):
    existing = [{"type": "AComponent", "guide": "pre-existing"}]
    (tmp_path / "processing.yaml").write_text(yaml.safe_dump(existing))

    entries = [GuideEntry(category="processing", component_type="AComponent", guide="new")]
    write_bundle(entries, tmp_path)

    merged = yaml.safe_load((tmp_path / "processing.yaml").read_text())
    guide_for_a = next(e for e in merged if e["type"] == "AComponent")["guide"]
    assert guide_for_a == "pre-existing"


def test_write_bundle_overwrites_when_flag_set(tmp_path: Path):
    existing = [{"type": "AComponent", "guide": "pre-existing"}]
    (tmp_path / "processing.yaml").write_text(yaml.safe_dump(existing))

    entries = [GuideEntry(category="processing", component_type="AComponent", guide="new")]
    write_bundle(entries, tmp_path, overwrite=True)

    merged = yaml.safe_load((tmp_path / "processing.yaml").read_text())
    guide_for_a = next(e for e in merged if e["type"] == "AComponent")["guide"]
    assert guide_for_a == "new"


def test_write_review_report(tmp_path: Path):
    rows = [
        ReportRow(component_type="AComponent", category="processing", completeness="rich", status="generated"),
        ReportRow(component_type="BComponent", category="processing", completeness="thin", status="generated"),
        ReportRow(component_type="CComponent", category="vectorstores", completeness="rich", status="skipped-existing"),
        ReportRow(component_type="DataMapperComponent", category="processing", completeness="rich", status="skipped-opted-out"),
    ]
    report_path = tmp_path / "review.md"
    write_review_report(rows, report_path)
    body = report_path.read_text()
    assert "BComponent" in body
    assert "thin" in body
    assert "Flagged for manual review" in body  # the thin-metadata callout
    assert "DataMapperComponent" in body  # opt-outs surfaced
    assert "opted out" in body.lower() or "skipped-opted-out" in body

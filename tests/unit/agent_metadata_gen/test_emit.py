"""Tests for the YAML bundle writer + report writer."""
from __future__ import annotations

from pathlib import Path

import yaml as _yaml

from scripts._agent_metadata_gen.emit import (
    GuideEntry,
    ReportRow,
    write_bundle,
    write_review_report,
)


def test_bundle_grouped_by_category_and_sorted(tmp_path: Path):
    entries = [
        GuideEntry(category="models", component_name="Beta", agent_summary="b", agent_usage_notes="bn"),
        GuideEntry(category="models", component_name="Alpha", agent_summary="a", agent_usage_notes="an"),
        GuideEntry(category="processing", component_name="Charlie", agent_summary="c", agent_usage_notes="cn"),
    ]
    write_bundle(entries, tmp_path, overwrite=True)

    models_path = tmp_path / "models.yaml"
    proc_path = tmp_path / "processing.yaml"
    assert models_path.exists() and proc_path.exists()

    models = _yaml.safe_load(models_path.read_text())
    assert [e["component_name"] for e in models] == ["Alpha", "Beta"]


def test_bundle_skips_existing_when_overwrite_false(tmp_path: Path):
    """Existing entries with matching component_name are kept verbatim."""
    (tmp_path / "models.yaml").write_text(
        "- component_name: Alpha\n  agent_summary: original\n  agent_usage_notes: original\n"
    )
    entries = [
        GuideEntry(category="models", component_name="Alpha", agent_summary="new", agent_usage_notes="new"),
        GuideEntry(category="models", component_name="Beta", agent_summary="b", agent_usage_notes="bn"),
    ]
    write_bundle(entries, tmp_path, overwrite=False)
    bundle = _yaml.safe_load((tmp_path / "models.yaml").read_text())
    by_name = {e["component_name"]: e for e in bundle}
    assert by_name["Alpha"]["agent_summary"] == "original"
    assert by_name["Beta"]["agent_summary"] == "b"


def test_bundle_overwrites_when_overwrite_true(tmp_path: Path):
    (tmp_path / "models.yaml").write_text(
        "- component_name: Alpha\n  agent_summary: original\n  agent_usage_notes: original\n"
    )
    entries = [
        GuideEntry(category="models", component_name="Alpha", agent_summary="new", agent_usage_notes="new"),
    ]
    write_bundle(entries, tmp_path, overwrite=True)
    bundle = _yaml.safe_load((tmp_path / "models.yaml").read_text())
    assert bundle[0]["agent_summary"] == "new"


def test_review_report_writes_markdown_table(tmp_path: Path):
    rows = [
        ReportRow(
            component_name="Alpha",
            category="models",
            metadata_completeness="rich",
            outcome="processed",
            summary_status="generated",
            usage_status="generated",
        ),
        ReportRow(
            component_name="Beta",
            category="models",
            metadata_completeness="thin",
            outcome="processed",
            summary_status="generated",
            usage_status="fallback-used",
        ),
        ReportRow(
            component_name="DataMapper",
            category="processing",
            metadata_completeness="rich",
            outcome="skipped-opted-out",
            summary_status="n/a",
            usage_status="n/a",
        ),
    ]
    out = tmp_path / "report.md"
    write_review_report(rows, out)
    text = out.read_text()
    assert "| Alpha | models | rich | processed | generated | generated |" in text
    assert "| Beta | models | thin | processed | generated | fallback-used |" in text
    assert "| DataMapper | processing | rich | skipped-opted-out | n/a | n/a |" in text

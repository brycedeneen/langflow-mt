"""Structural tests for the ADP Worker Sync to SFTP starter template.

The template is the simplified 4-node shape: ADP Trigger → Type Convert →
Structured Output → SFTP CSV Upload. The Type Convert node bridges the
Data → Message type gap before Structured Output extracts the user-defined
fields and emits a DataFrame for SFTP to write as CSV.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# JSON source files have been moved to the alembic fixtures directory after
# being imported into the DB as Template rows during the D-phase migration.
TEMPLATE_PATH = (
    Path(__file__).resolve().parents[3]
    / "base"
    / "langflow"
    / "alembic"
    / "versions"
    / "category_rework_fixtures"
    / "ADP Worker Sync to SFTP.json"
)


@pytest.fixture(scope="module")
def template() -> dict:
    with TEMPLATE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def test_template_top_level_metadata(template):
    assert template["name"] == "ADP Worker Sync to SFTP"
    assert "ADP" in template["description"] and "SFTP" in template["description"]


def test_template_has_four_nodes_with_expected_types(template):
    nodes = template["data"]["nodes"]
    assert len(nodes) == 4
    types = sorted(n["data"]["type"] for n in nodes)
    assert types == sorted(
        ["ADPTrigger", "TypeConverterComponent", "StructuredOutput", "SFTPCSVUpload"]
    )


def test_template_has_three_edges(template):
    edges = template["data"]["edges"]
    assert len(edges) == 3


def _node_by_type(template, type_name):
    return next(n for n in template["data"]["nodes"] if n["data"]["type"] == type_name)


def test_adp_trigger_event_types_default(template):
    trigger = _node_by_type(template, "ADPTrigger")
    event_types = trigger["data"]["node"]["template"]["event_types"]["value"]
    assert "New Hire" in event_types
    assert "Retirement" in event_types
    assert "Deceased" in event_types


def test_adp_trigger_event_types_marked_as_list(template):
    """The frontend dispatcher routes to MultiselectComponent only when
    `templateData.list === true`. Without this key the field renders as a
    single-select DropdownComponent, which can't hold the array value and
    drops it during template→flow clone. Both observed bugs (value strip
    + single-select dropdown) trace back to this missing serialization.
    Hand-built MultiselectInput templates must include `list: true`.
    """
    trigger = _node_by_type(template, "ADPTrigger")
    event_types = trigger["data"]["node"]["template"]["event_types"]
    assert event_types.get("list") is True, (
        "MultiselectInput template must serialize `list: true` so the "
        "frontend renders MultiselectComponent (multi-select with chips). "
        "If absent, the dispatcher falls through to DropdownComponent "
        "(single-select) and the array value is stripped on clone."
    )


def test_type_convert_emits_message(template):
    converter = _node_by_type(template, "TypeConverterComponent")
    output_type = converter["data"]["node"]["template"]["output_type"]["value"]
    assert output_type == "Message"


def test_structured_output_defaults_filled(template):
    so = _node_by_type(template, "StructuredOutput")
    template_dict = so["data"]["node"]["template"]
    model_value = template_dict["model"]["value"]
    assert isinstance(model_value, list) and len(model_value) >= 1
    selected = model_value[0]
    assert selected["provider"] == "Anthropic"
    assert "haiku" in selected["name"].lower()
    # output_schema starts empty; assistant appends rows per user-chosen fields
    assert template_dict["output_schema"]["value"] == []


def test_sftp_node_per_flow_fields_empty(template):
    sftp = _node_by_type(template, "SFTPCSVUpload")
    template_dict = sftp["data"]["node"]["template"]
    assert template_dict["host"]["value"] == ""
    assert template_dict["username"]["value"] == ""
    assert template_dict["password"]["value"] == ""
    assert template_dict["filename"]["value"] == ""
    assert template_dict["port"]["value"] == 22


def test_metadata_sibling_file_present_and_well_formed():
    # The metadata.json remains in the original starter_projects directory
    # (not in the alembic fixtures), as it's consumed by create_or_update_template_metadata.
    sibling = (
        Path(__file__).resolve().parents[3]
        / "base"
        / "langflow"
        / "initial_setup"
        / "starter_projects"
        / "ADP Worker Sync to SFTP.metadata.json"
    )
    assert sibling.exists()
    with sibling.open(encoding="utf-8") as f:
        meta = json.load(f)
    assert meta.get("agent_summary")
    assert meta.get("agent_usage_notes")
    notes = meta["agent_usage_notes"]
    assert "create_secret_variable" in notes
    assert "get_webhook_credentials" in notes
    # ADP credentials preflight is gone (no ADP API calls in the simplified flow)
    assert "adp_client_id" not in notes

"""Tests for create_or_update_template_metadata.

Seeder behavior (per spec):
- First seed (no row exists) -> INSERT with updated_by=NULL.
- Re-seed when updated_by IS NULL -> UPDATE (overwrite from file).
- Re-seed when updated_by IS NOT NULL -> SKIP (admin took ownership).
- Missing matching flow -> log + skip, no raise.
- Malformed JSON -> log + skip, doesn't break sibling templates.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlmodel import select

from langflow.initial_setup.constants import STARTER_FOLDER_NAME
from langflow.initial_setup.setup import (
    create_or_update_template_metadata,
    get_or_create_starter_folder,
    session_scope,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.template_metadata.model import TemplateMetadata


async def _seed_starter_folder_id() -> "uuid4().__class__":
    async with session_scope() as session:
        folder = await get_or_create_starter_folder(session)
        return folder.id


async def _seed_flow(folder_id, name: str):
    async with session_scope() as session:
        flow = Flow(
            name=name,
            description="test",
            folder_id=folder_id,
            data={"nodes": [], "edges": []},
        )
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        return flow.id


async def _fetch_metadata_rows(flow_id=None):
    async with session_scope() as session:
        stmt = select(TemplateMetadata)
        if flow_id is not None:
            stmt = stmt.where(TemplateMetadata.flow_id == flow_id)
        return (await session.exec(stmt)).all()


def _write_metadata_file(tmp_dir: Path, flow_name: str, summary: str, notes: str) -> Path:
    p = tmp_dir / f"{flow_name}.metadata.json"
    p.write_text(json.dumps({"agent_summary": summary, "agent_usage_notes": notes}))
    # Also create a placeholder flow JSON so the directory matches real layout
    (tmp_dir / f"{flow_name}.json").write_text(
        json.dumps({"name": flow_name, "data": {"nodes": [], "edges": []}})
    )
    return p


@pytest.mark.usefixtures("client")
async def test_first_seed_creates_row_with_null_updated_by(tmp_path):
    folder_id = await _seed_starter_folder_id()
    flow_id = await _seed_flow(folder_id, "Sample Template")
    _write_metadata_file(tmp_path, "Sample Template", "Summary one", "Notes one")

    await create_or_update_template_metadata(starter_projects_dir=tmp_path)

    rows = await _fetch_metadata_rows(flow_id=flow_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.agent_summary == "Summary one"
    assert row.agent_usage_notes == "Notes one"
    assert row.updated_by is None


@pytest.mark.usefixtures("client")
async def test_reseed_overwrites_when_updated_by_is_null(tmp_path):
    folder_id = await _seed_starter_folder_id()
    flow_id = await _seed_flow(folder_id, "Sample Template Two")
    _write_metadata_file(tmp_path, "Sample Template Two", "Summary one", "Notes one")
    await create_or_update_template_metadata(starter_projects_dir=tmp_path)

    # Edit the file and re-seed
    _write_metadata_file(tmp_path, "Sample Template Two", "Summary TWO", "Notes TWO")
    await create_or_update_template_metadata(starter_projects_dir=tmp_path)

    rows = await _fetch_metadata_rows(flow_id=flow_id)
    assert len(rows) == 1
    assert rows[0].agent_summary == "Summary TWO"
    assert rows[0].agent_usage_notes == "Notes TWO"


@pytest.mark.usefixtures("client")
async def test_reseed_skips_when_admin_has_edited(tmp_path):
    folder_id = await _seed_starter_folder_id()
    flow_id = await _seed_flow(folder_id, "Sample Template Three")
    _write_metadata_file(tmp_path, "Sample Template Three", "Summary one", "Notes one")
    await create_or_update_template_metadata(starter_projects_dir=tmp_path)

    # Simulate admin edit: set updated_by to a non-null UUID
    async with session_scope() as session:
        row = (
            await session.exec(
                select(TemplateMetadata).where(TemplateMetadata.flow_id == flow_id)
            )
        ).one()
        row.updated_by = uuid4()
        row.agent_summary = "Admin Edited Summary"
        session.add(row)
        await session.commit()

    # Edit the file again and re-seed
    _write_metadata_file(tmp_path, "Sample Template Three", "Summary THREE", "Notes THREE")
    await create_or_update_template_metadata(starter_projects_dir=tmp_path)

    rows = await _fetch_metadata_rows(flow_id=flow_id)
    assert len(rows) == 1
    assert rows[0].agent_summary == "Admin Edited Summary"  # unchanged


@pytest.mark.usefixtures("client")
async def test_missing_flow_is_logged_and_skipped(tmp_path):
    """Sibling metadata file present, but no matching seeded flow -> skip, don't raise."""
    # Make sure the starter folder exists so the seeder gets that far
    await _seed_starter_folder_id()
    _write_metadata_file(tmp_path, "Nonexistent Template Xyz", "x", "y")

    # Should not raise
    await create_or_update_template_metadata(starter_projects_dir=tmp_path)

    # No metadata row was created for the nonexistent flow
    async with session_scope() as session:
        stmt = select(TemplateMetadata).join(Flow).where(Flow.name == "Nonexistent Template Xyz")
        rows = (await session.exec(stmt)).all()
    assert rows == []


@pytest.mark.usefixtures("client")
async def test_malformed_json_is_logged_and_skipped(tmp_path):
    folder_id = await _seed_starter_folder_id()
    good_flow_id = await _seed_flow(folder_id, "Good Template Seed")
    _write_metadata_file(tmp_path, "Good Template Seed", "good summary", "good notes")

    # Add a malformed sibling for a different (also seeded) flow
    bad_flow_id = await _seed_flow(folder_id, "Bad Template Seed")
    (tmp_path / "Bad Template Seed.json").write_text(
        json.dumps({"name": "Bad Template Seed", "data": {"nodes": [], "edges": []}})
    )
    (tmp_path / "Bad Template Seed.metadata.json").write_text("{this is not valid json")

    # Should not raise
    await create_or_update_template_metadata(starter_projects_dir=tmp_path)

    # Good Template's metadata still got seeded
    good_rows = await _fetch_metadata_rows(flow_id=good_flow_id)
    assert len(good_rows) == 1
    assert good_rows[0].agent_summary == "good summary"
    # Bad Template has no row
    bad_rows = await _fetch_metadata_rows(flow_id=bad_flow_id)
    assert bad_rows == []

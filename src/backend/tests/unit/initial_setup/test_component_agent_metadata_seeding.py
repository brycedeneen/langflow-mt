"""Tests for create_or_update_component_agent_metadata.

Seeder behavior (per spec):
- First seed (no row exists) -> INSERT with updated_by=NULL.
- Re-seed when updated_by IS NULL -> UPDATE (overwrite from YAML).
- Re-seed when updated_by IS NOT NULL -> SKIP (admin took ownership).
- Malformed YAML file -> log + skip, doesn't break sibling files.
- Concurrent INSERT race -> IntegrityError swallowed; no exception bubbled.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from langflow.initial_setup.setup import (
    create_or_update_component_agent_metadata,
    session_scope,
)
from langflow.services.database.models.component_metadata.model import ComponentMetadata
from sqlmodel import select

if TYPE_CHECKING:
    from pathlib import Path


def _write_yaml(dir_path: Path, filename: str, body: str) -> None:
    (dir_path / filename).write_text(body)


async def _fetch_metadata(component_name: str) -> ComponentMetadata | None:
    async with session_scope() as session:
        return (
            await session.exec(
                select(ComponentMetadata).where(
                    ComponentMetadata.component_name == component_name
                )
            )
        ).first()


@pytest.mark.asyncio
@pytest.mark.usefixtures("client")
async def test_first_seed_inserts_row(tmp_path: Path):
    _write_yaml(
        tmp_path,
        "models.yaml",
        "- component_name: OpenAIModel\n"
        "  agent_summary: One-line summary.\n"
        "  agent_usage_notes: |\n"
        "    ## What it does\n"
        "    Calls OpenAI.\n",
    )
    await create_or_update_component_agent_metadata(yaml_dir=tmp_path)

    row = await _fetch_metadata("OpenAIModel")
    assert row is not None
    assert row.agent_summary == "One-line summary."
    assert "## What it does" in row.agent_usage_notes
    assert row.updated_by is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("client")
async def test_reseed_updates_when_updated_by_is_null(tmp_path: Path):
    _write_yaml(
        tmp_path,
        "models.yaml",
        "- component_name: OpenAIModel\n"
        "  agent_summary: Original.\n"
        "  agent_usage_notes: original notes\n",
    )
    await create_or_update_component_agent_metadata(yaml_dir=tmp_path)

    # Regenerate with new content, re-seed.
    _write_yaml(
        tmp_path,
        "models.yaml",
        "- component_name: OpenAIModel\n"
        "  agent_summary: Updated.\n"
        "  agent_usage_notes: updated notes\n",
    )
    await create_or_update_component_agent_metadata(yaml_dir=tmp_path)

    row = await _fetch_metadata("OpenAIModel")
    assert row.agent_summary == "Updated."
    assert row.agent_usage_notes == "updated notes"
    assert row.updated_by is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("client")
async def test_reseed_skips_when_admin_owned(tmp_path: Path):
    _write_yaml(
        tmp_path,
        "models.yaml",
        "- component_name: OpenAIModel\n"
        "  agent_summary: Original.\n"
        "  agent_usage_notes: original notes\n",
    )
    await create_or_update_component_agent_metadata(yaml_dir=tmp_path)

    admin_id = uuid4()
    async with session_scope() as session:
        row = (
            await session.exec(
                select(ComponentMetadata).where(
                    ComponentMetadata.component_name == "OpenAIModel"
                )
            )
        ).first()
        row.agent_summary = "Admin-edited."
        row.updated_by = admin_id
        session.add(row)

    # Re-seed with new YAML content; admin row must not be overwritten.
    _write_yaml(
        tmp_path,
        "models.yaml",
        "- component_name: OpenAIModel\n"
        "  agent_summary: Should-not-overwrite.\n"
        "  agent_usage_notes: nope\n",
    )
    await create_or_update_component_agent_metadata(yaml_dir=tmp_path)

    row = await _fetch_metadata("OpenAIModel")
    assert row.agent_summary == "Admin-edited."
    assert row.updated_by == admin_id


@pytest.mark.asyncio
@pytest.mark.usefixtures("client")
async def test_malformed_yaml_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from langflow.initial_setup import setup as setup_module

    _write_yaml(tmp_path, "good.yaml", "- component_name: GoodComp\n  agent_summary: G\n  agent_usage_notes: g\n")
    _write_yaml(tmp_path, "bad.yaml", "::: not: yaml [\n")

    warn_messages: list[str] = []
    original_awarning = setup_module.logger.awarning

    async def _capture_awarning(msg, *args, **kwargs):
        warn_messages.append(str(msg))
        return await original_awarning(msg, *args, **kwargs)

    monkeypatch.setattr(setup_module.logger, "awarning", _capture_awarning)
    await create_or_update_component_agent_metadata(yaml_dir=tmp_path)

    assert await _fetch_metadata("GoodComp") is not None
    assert any("bad.yaml" in line for line in warn_messages)


@pytest.mark.asyncio
@pytest.mark.usefixtures("client")
async def test_no_yaml_files_is_noop(tmp_path: Path):
    # Empty directory should not raise and not create any rows.
    await create_or_update_component_agent_metadata(yaml_dir=tmp_path)
    async with session_scope() as session:
        all_rows = (await session.exec(select(ComponentMetadata))).all()
    # Filter to a sentinel name that the test owns:
    assert not any(r.component_name == "GoodComp" for r in all_rows)

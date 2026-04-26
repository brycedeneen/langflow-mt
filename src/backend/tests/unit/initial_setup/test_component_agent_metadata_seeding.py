"""Tests for create_or_update_component_agent_metadata.

Seeder behavior (per spec):
- First seed (no row exists) -> INSERT with updated_by=NULL.
- Re-seed when updated_by IS NULL -> UPDATE (overwrite from YAML).
- Re-seed when updated_by IS NOT NULL -> SKIP (admin took ownership).
- YAML entries are normalised: any alias (class name, display name, registry key)
  is resolved to the canonical registry key before the DB write.
- Unresolvable entries (no matching live component) -> log + skip, no row written.
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


@pytest.fixture
def stub_aliases(monkeypatch: pytest.MonkeyPatch):
    """Patch the live-catalog resolver with a controlled alias map for tests."""

    def _stub(mapping: dict[str, str]) -> None:
        async def _build():
            return mapping

        from langflow.agentic.utils import component_search

        monkeypatch.setattr(component_search, "build_component_name_resolver", _build)

    return _stub


@pytest.mark.asyncio
@pytest.mark.usefixtures("client")
async def test_first_seed_inserts_row(tmp_path: Path, stub_aliases):
    stub_aliases({"OpenAIModel": "OpenAIModel"})
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
async def test_seeder_resolves_class_name_alias(tmp_path: Path, stub_aliases):
    """A YAML entry keyed by the Python class name is normalised to the registry key."""
    stub_aliases({"OpenAIModelComponent": "OpenAIModel", "OpenAIModel": "OpenAIModel"})
    _write_yaml(
        tmp_path,
        "models.yaml",
        "- component_name: OpenAIModelComponent\n"
        "  agent_summary: From class-name YAML.\n"
        "  agent_usage_notes: notes.\n",
    )
    await create_or_update_component_agent_metadata(yaml_dir=tmp_path)

    canonical = await _fetch_metadata("OpenAIModel")
    aliased = await _fetch_metadata("OpenAIModelComponent")
    assert canonical is not None
    assert canonical.agent_summary == "From class-name YAML."
    assert aliased is None, "Row must not be written under the class-name alias."


@pytest.mark.asyncio
@pytest.mark.usefixtures("client")
async def test_seeder_skips_unresolvable_entry(tmp_path: Path, stub_aliases):
    """Entries whose component_name doesn't match any live component are skipped."""
    stub_aliases({"OpenAIModel": "OpenAIModel"})
    _write_yaml(
        tmp_path,
        "models.yaml",
        "- component_name: NoLongerExistsComponent\n"
        "  agent_summary: ignored\n"
        "  agent_usage_notes: ignored\n",
    )
    await create_or_update_component_agent_metadata(yaml_dir=tmp_path)
    assert await _fetch_metadata("NoLongerExistsComponent") is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("client")
async def test_reseed_updates_when_updated_by_is_null(tmp_path: Path, stub_aliases):
    stub_aliases({"OpenAIModel": "OpenAIModel"})
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
async def test_reseed_skips_when_admin_owned(tmp_path: Path, stub_aliases):
    stub_aliases({"OpenAIModel": "OpenAIModel"})
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
async def test_malformed_yaml_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stub_aliases):
    from langflow.initial_setup import setup as setup_module

    stub_aliases({"GoodComp": "GoodComp"})
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
async def test_no_yaml_files_is_noop(tmp_path: Path, stub_aliases):
    stub_aliases({})
    # Empty directory should not raise and not create any rows.
    await create_or_update_component_agent_metadata(yaml_dir=tmp_path)
    async with session_scope() as session:
        all_rows = (await session.exec(select(ComponentMetadata))).all()
    # Filter to a sentinel name that the test owns:
    assert not any(r.component_name == "GoodComp" for r in all_rows)

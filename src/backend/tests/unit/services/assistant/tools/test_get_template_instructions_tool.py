"""Unit tests for get_template_instructions tool."""

from __future__ import annotations

import pytest

from langflow.services.assistant.tools.template_metadata import get_template_instructions
from langflow.services.database.models.template.model import Template
from langflow.services.deps import session_scope


@pytest.mark.asyncio
async def test_returns_usage_notes_when_notes_authored(active_super_user):  # noqa: ARG001
    async with session_scope() as session:
        template = Template(
            name="Onboard-tool-test-a",
            scope="platform",
            nodes=[],
            edges=[],
            agent_usage_notes="Ask for Slack channel, then wire it.",
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)
        template_id_str = str(template.id)

    result = await get_template_instructions(template_id_str)
    assert result is not None
    assert result["template_id"] == template_id_str
    assert result["template_name"] == "Onboard-tool-test-a"
    assert result["agent_usage_notes"] == "Ask for Slack channel, then wire it."


@pytest.mark.asyncio
async def test_returns_null_notes_when_notes_not_authored(active_super_user):  # noqa: ARG001
    async with session_scope() as session:
        template = Template(
            name="Onboard-tool-test-b",
            scope="platform",
            nodes=[],
            edges=[],
            # no agent_usage_notes
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)
        template_id_str = str(template.id)

    result = await get_template_instructions(template_id_str)
    assert result is not None
    assert result["agent_usage_notes"] is None


@pytest.mark.asyncio
async def test_returns_none_when_template_missing():
    result = await get_template_instructions("00000000-0000-0000-0000-000000000000")
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_when_template_id_unparseable():
    result = await get_template_instructions("not-a-uuid")
    assert result is None

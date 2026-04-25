"""Unit tests for template-summary system-prompt block."""

from __future__ import annotations

import pytest

from langflow.services.assistant.template_prompt import build_available_templates_block
from langflow.services.database.models.template.model import Template
from langflow.services.deps import session_scope


@pytest.mark.asyncio
async def test_empty_when_no_summaries():
    text = await build_available_templates_block()
    assert text == ""


@pytest.mark.asyncio
async def test_block_lists_templates_with_summaries_sorted(active_super_user):  # noqa: ARG001
    names = ["Zeta-prompt-Template", "Alpha-prompt-Template"]
    ids = []
    async with session_scope() as session:
        for n in names:
            t = Template(
                name=n,
                scope="platform",
                nodes=[],
                edges=[],
                agent_summary=f"{n.split('-')[0]} summary.",
            )
            session.add(t)
            await session.commit()
            await session.refresh(t)
            ids.append(t.id)

    text = await build_available_templates_block()
    assert "## Available Templates" in text
    # Sorted by template name: Alpha before Zeta
    assert text.index("Alpha-prompt-Template") < text.index("Zeta-prompt-Template")
    assert "Alpha summary." in text
    assert "Zeta summary." in text
    for tid in ids:
        assert str(tid) in text


@pytest.mark.asyncio
async def test_block_excludes_templates_with_null_summary(active_super_user):  # noqa: ARG001
    async with session_scope() as session:
        t = Template(
            name="SilentPromptTemplate",
            scope="platform",
            nodes=[],
            edges=[],
            # no agent_summary
        )
        session.add(t)
        await session.commit()

    text = await build_available_templates_block()
    assert "SilentPromptTemplate" not in text

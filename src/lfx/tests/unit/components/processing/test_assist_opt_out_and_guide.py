"""DataMapper opts out of ADP Assist; TextOperations carries a reference guide."""

from __future__ import annotations

import pytest

from langflow.services.component_assist.guide_registry import (
    is_assist_enabled,
    resolve,
)
from lfx.components.processing.data_mapper import DataMapperComponent
from lfx.components.processing.text_operations import TextOperations


def test_data_mapper_opts_out_of_assist():
    assert is_assist_enabled(DataMapperComponent) is False


@pytest.mark.asyncio
async def test_text_operations_has_assist_guide(monkeypatch: pytest.MonkeyPatch):
    # `resolve()` is async and consults `component_metadata` first; this test
    # exercises the class-attribute fallback (TextOperations carries an
    # `assist_guide` class attr), so stub the DB lookup to None.
    async def _no_db_row(_name: str) -> str | None:
        return None

    monkeypatch.setattr(
        "langflow.services.component_assist.guide_registry.fetch_component_usage_notes",
        _no_db_row,
    )
    guide = await resolve(TextOperations)
    assert isinstance(guide, str)
    assert len(guide) > 200
    assert is_assist_enabled(TextOperations) is True


def test_default_components_remain_opted_in():
    # Sanity: a component that doesn't override stays opt-in by default.
    from lfx.components.processing.combine_text import CombineTextComponent

    assert is_assist_enabled(CombineTextComponent) is True

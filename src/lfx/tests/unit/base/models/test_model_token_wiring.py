"""Tests for `_model_name` stamping in LCModelComponent._get_chat_result()."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from lfx.base.models.model import LCModelComponent


def _make_lc_model_component(*, model_name: str | None = None, model_attr: str | None = None) -> LCModelComponent:
    """Return a minimal LCModelComponent stub bypassing Component.__init__."""
    component = LCModelComponent.__new__(LCModelComponent)
    component._token_usage = None
    component._model_name = None
    component.display_name = "Fake"
    component.status = None
    if model_name is not None:
        component.model_name = model_name
    if model_attr is not None:
        component.model = model_attr
    component.get_langchain_callbacks = MagicMock(return_value=[])
    component.get_project_name = MagicMock(return_value="test")
    component.is_connected_to_chat_output = MagicMock(return_value=False)
    component.build_status_message = MagicMock(return_value="ok")
    return component


def _make_runnable_returning(message: AIMessage):
    """Construct a runnable mock whose with_config().ainvoke() resolves to message."""
    runnable = MagicMock()
    configured = MagicMock()
    configured.ainvoke = AsyncMock(return_value=message)
    runnable.with_config.return_value = configured
    return runnable


@pytest.mark.asyncio
async def test_model_component_stamps_model_name_alongside_token_usage():
    """When LCModelComponent extracts usage from an AIMessage, it also stamps _model_name."""
    component = _make_lc_model_component(model_name="gpt-4o-mini")

    ai_message = AIMessage(
        content="hi",
        response_metadata={
            "token_usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8}
        },
    )
    runnable = _make_runnable_returning(ai_message)

    await component._get_chat_result(
        runnable=runnable,
        stream=False,
        input_value="hello",
        system_message=None,
    )

    assert component._token_usage is not None
    assert component._model_name == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_model_component_falls_back_to_model_attr_when_no_model_name():
    """If `model_name` is missing but `model` is present, _model_name takes the latter."""
    component = _make_lc_model_component(model_attr="claude-3-haiku")

    ai_message = AIMessage(
        content="hi",
        response_metadata={
            "token_usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}
        },
    )
    runnable = _make_runnable_returning(ai_message)

    await component._get_chat_result(
        runnable=runnable,
        stream=False,
        input_value="hello",
        system_message=None,
    )

    assert component._token_usage is not None
    assert component._model_name == "claude-3-haiku"

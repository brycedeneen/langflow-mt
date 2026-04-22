"""Unit tests for ``_ProviderLLMAdapter`` tool-schema conversion.

The component-assist service defines tools in the internal ``{name, description,
parameters}`` registry format. The adapter must convert those into each
provider's native tool format before calling ``stream_with_tools`` — otherwise
the Anthropic API rejects the request with ``tools.0.custom.input_schema:
Field required``.
"""
from __future__ import annotations

# ruff: noqa: ARG002  -- ProviderClient interface stubs take positional args we don't use.
from typing import TYPE_CHECKING, Any

import pytest
from langflow.api.v1.component_assist import _ProviderLLMAdapter
from langflow.services.assistant.providers.anthropic_provider import AnthropicProviderClient
from langflow.services.assistant.providers.base import ProviderClient, StreamEvent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class _CapturingOpenAIProvider(ProviderClient):
    """Non-Anthropic provider that captures the `tools` arg."""

    def __init__(self) -> None:
        self.captured_tools: list[dict[str, Any]] | None = None

    async def stream_with_tools(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[StreamEvent]:
        self.captured_tools = tools
        if False:  # pragma: no cover — async generator hint
            yield

    async def stream_with_tool_results(self, *args, **kwargs) -> AsyncIterator[StreamEvent]:
        if False:  # pragma: no cover
            yield
        return


class _CapturingAnthropicProvider(AnthropicProviderClient):
    """Anthropic subclass that captures the `tools` arg without hitting the API."""

    def __init__(self) -> None:
        # Skip parent __init__ — we don't want a real client.
        self.captured_tools: list[dict[str, Any]] | None = None

    async def stream_with_tools(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[StreamEvent]:
        self.captured_tools = tools
        if False:  # pragma: no cover
            yield

    async def stream_with_tool_results(self, *args, **kwargs) -> AsyncIterator[StreamEvent]:
        if False:  # pragma: no cover
            yield
        return


_INTERNAL_TOOL = {
    "name": "propose_config_update",
    "description": "propose a patch",
    "parameters": {"type": "object", "properties": {"x": {"type": "integer"}}, "required": []},
}


@pytest.mark.asyncio
async def test_adapter_converts_tools_to_anthropic_native_format():
    provider = _CapturingAnthropicProvider()
    adapter = _ProviderLLMAdapter(provider)

    gen = await adapter.stream(
        system_prompt="sys",
        thread=[],
        user_message="hi",
        tools=[_INTERNAL_TOOL],
    )
    async for _ in gen:
        pass

    assert provider.captured_tools == [
        {
            "name": "propose_config_update",
            "description": "propose a patch",
            "input_schema": {
                "type": "object",
                "properties": {"x": {"type": "integer"}},
                "required": [],
            },
        }
    ]


@pytest.mark.asyncio
async def test_adapter_converts_tools_to_openai_native_format():
    provider = _CapturingOpenAIProvider()
    adapter = _ProviderLLMAdapter(provider)

    gen = await adapter.stream(
        system_prompt="sys",
        thread=[],
        user_message="hi",
        tools=[_INTERNAL_TOOL],
    )
    async for _ in gen:
        pass

    assert provider.captured_tools == [
        {
            "type": "function",
            "function": {
                "name": "propose_config_update",
                "description": "propose a patch",
                "parameters": {
                    "type": "object",
                    "properties": {"x": {"type": "integer"}},
                    "required": [],
                },
            },
        }
    ]

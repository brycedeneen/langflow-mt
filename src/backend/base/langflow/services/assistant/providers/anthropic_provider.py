"""Anthropic provider adapter for the assistant service."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from langflow.services.assistant.providers.base import ProviderClient, StreamEvent, ToolResult
from langflow.services.assistant.tools.registry import get_tools_for_anthropic


class AnthropicProviderClient(ProviderClient):
    """Provider that streams responses from the Anthropic Messages API."""

    def __init__(self, api_key: str, model: str):
        self._api_key = api_key
        self._model = model
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    # ------------------------------------------------------------------
    # Message conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert internal message format to Anthropic API format.

        - role=tool  ->  user message with tool_result content block
        - assistant with tool_calls  ->  assistant message with tool_use blocks
        """
        anthropic_messages: list[dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")

            if role == "assistant" and "tool_calls" in msg:
                content: list[dict[str, Any]] = []
                # Include any text the assistant produced before tool calls
                if msg.get("content"):
                    content.append({"type": "text", "text": msg["content"]})
                for tc in msg["tool_calls"]:
                    content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc.get("args", {}),
                    })
                anthropic_messages.append({"role": "assistant", "content": content})

            elif role == "tool":
                anthropic_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg["tool_call_id"],
                            "content": msg.get("content", ""),
                        }
                    ],
                })

            else:
                anthropic_messages.append({
                    "role": role,
                    "content": msg.get("content", ""),
                })

        return anthropic_messages

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def _stream(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[StreamEvent]:
        """Core streaming implementation shared by both entry-points."""
        client = self._get_client()
        anthropic_messages = self._convert_messages(messages)

        # Use Anthropic-native tool format; fall back to registry if caller
        # passed OpenAI-style definitions.
        if tools:
            anthropic_tools = tools
        else:
            anthropic_tools = get_tools_for_anthropic()

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": anthropic_messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        # Track current tool_use block while streaming
        current_tool_id: str | None = None
        current_tool_name: str | None = None
        json_acc: str = ""
        stop_reason: str | None = None

        try:
            async with client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    event_type = event.type

                    if event_type == "content_block_start":
                        block = event.content_block
                        if block.type == "tool_use":
                            current_tool_id = block.id
                            current_tool_name = block.name
                            json_acc = ""

                    elif event_type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta":
                            yield StreamEvent(type="token", text=delta.text)
                        elif delta.type == "input_json_delta":
                            json_acc += delta.partial_json

                    elif event_type == "content_block_stop":
                        if current_tool_id is not None:
                            try:
                                args = json.loads(json_acc) if json_acc else {}
                            except json.JSONDecodeError:
                                args = {}
                            yield StreamEvent(
                                type="tool_call",
                                tool_call_id=current_tool_id,
                                tool_name=current_tool_name,
                                tool_args=args,
                            )
                            current_tool_id = None
                            current_tool_name = None
                            json_acc = ""

                    elif event_type == "message_delta":
                        stop_reason = getattr(event.delta, "stop_reason", None)

                    elif event_type == "message_stop":
                        if stop_reason != "tool_use":
                            yield StreamEvent(type="message_complete")
        except Exception as exc:
            from anthropic import APIError, AuthenticationError, RateLimitError

            if isinstance(exc, RateLimitError):
                msg = "Rate limit exceeded. Please wait a moment and try again."
            elif isinstance(exc, AuthenticationError):
                msg = "Invalid API key. Please check your Anthropic API key configuration."
            elif isinstance(exc, APIError):
                msg = f"Anthropic API error: {exc}"
            else:
                raise
            yield StreamEvent(type="error", error_message=msg)

    async def stream_with_tools(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[StreamEvent]:
        async for event in self._stream(messages, system_prompt, tools):
            yield event

    async def stream_with_tool_results(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
        tool_results: list[ToolResult],
    ) -> AsyncIterator[StreamEvent]:
        # tool_results are already encoded in messages by the caller
        async for event in self._stream(messages, system_prompt, tools):
            yield event

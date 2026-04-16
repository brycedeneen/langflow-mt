"""OpenAI provider adapter for the assistant service."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from langflow.services.assistant.providers.base import ProviderClient, StreamEvent, ToolResult


class OpenAIProviderClient(ProviderClient):
    """Provider that streams responses from the OpenAI Chat Completions API."""

    def __init__(self, api_key: str, model: str):
        self._api_key = api_key
        self._model = model
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    # ------------------------------------------------------------------
    # Message conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_messages(messages: list[dict[str, Any]], system_prompt: str) -> list[dict[str, Any]]:
        """Convert internal message format to OpenAI API format."""
        openai_messages: list[dict[str, Any]] = []

        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            role = msg.get("role", "user")

            if role == "assistant" and "tool_calls" in msg:
                # Format tool calls in OpenAI function-calling style
                tool_calls = []
                for tc in msg["tool_calls"]:
                    tool_calls.append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["args"]) if isinstance(tc["args"], dict) else tc["args"],
                        },
                    })
                openai_messages.append({
                    "role": "assistant",
                    "content": msg.get("content"),
                    "tool_calls": tool_calls,
                })
            elif role == "tool":
                openai_messages.append({
                    "role": "tool",
                    "tool_call_id": msg["tool_call_id"],
                    "content": msg.get("content", ""),
                })
            else:
                openai_messages.append({
                    "role": role,
                    "content": msg.get("content", ""),
                })

        return openai_messages

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
        openai_messages = self._convert_messages(messages, system_prompt)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": openai_messages,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools

        stream = await client.chat.completions.create(**kwargs)

        # Accumulate tool call deltas by index
        tool_calls_acc: dict[int, dict[str, Any]] = {}

        async for chunk in stream:
            choice = chunk.choices[0] if chunk.choices else None
            if choice is None:
                continue

            delta = choice.delta

            # Content tokens
            if delta and delta.content:
                yield StreamEvent(type="token", text=delta.content)

            # Tool call deltas
            if delta and delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {
                            "id": tc_delta.id or "",
                            "name": "",
                            "arguments": "",
                        }
                    if tc_delta.id:
                        tool_calls_acc[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls_acc[idx]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls_acc[idx]["arguments"] += tc_delta.function.arguments

            # Finish reasons
            if choice.finish_reason == "tool_calls":
                for idx in sorted(tool_calls_acc.keys()):
                    tc = tool_calls_acc[idx]
                    try:
                        args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    except json.JSONDecodeError:
                        args = {}
                    yield StreamEvent(
                        type="tool_call",
                        tool_call_id=tc["id"],
                        tool_name=tc["name"],
                        tool_args=args,
                    )
                tool_calls_acc.clear()
            elif choice.finish_reason == "stop":
                yield StreamEvent(type="message_complete")

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

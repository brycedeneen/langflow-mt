from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class StreamEvent:
    """A single event from the provider stream."""
    type: str  # "token", "tool_call", "tool_result_request", "message_complete", "error"
    text: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    error_message: str | None = None


@dataclass
class ToolResult:
    tool_call_id: str
    content: str


class ProviderClient(ABC):
    @abstractmethod
    async def stream_with_tools(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[StreamEvent]:
        """Stream a single LLM turn. Yields StreamEvents. Stops at message end or tool_calls."""
        ...

    @abstractmethod
    async def stream_with_tool_results(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
        tool_results: list[ToolResult],
    ) -> AsyncIterator[StreamEvent]:
        """Continue after tool execution. Adds tool results to messages and streams next turn."""
        ...


@dataclass
class ScriptedTurn:
    """A scripted sequence of events the fake provider should emit."""
    events: list[StreamEvent] = field(default_factory=list)


class FakeProviderClient(ProviderClient):
    """Test double that replays scripted turns."""

    def __init__(self, turns: list[ScriptedTurn]):
        self._turns = list(turns)
        self._turn_index = 0

    async def stream_with_tools(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[StreamEvent]:
        if self._turn_index >= len(self._turns):
            yield StreamEvent(type="error", error_message="No more scripted turns")
            return
        turn = self._turns[self._turn_index]
        self._turn_index += 1
        for event in turn.events:
            yield event

    async def stream_with_tool_results(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
        tool_results: list[ToolResult],
    ) -> AsyncIterator[StreamEvent]:
        if self._turn_index >= len(self._turns):
            yield StreamEvent(type="error", error_message="No more scripted turns")
            return
        turn = self._turns[self._turn_index]
        self._turn_index += 1
        for event in turn.events:
            yield event

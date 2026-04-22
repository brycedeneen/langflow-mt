"""Per-component ephemeral assistant service.

Stateless: every call to ``stream_reply`` is a fresh request carrying the full thread.
No DB writes, no in-process session cache.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from langflow.services.component_assist.prompt import build_system_prompt
from langflow.services.component_assist.schemas import (
    ComponentAssistRequest,
    ProposeConfigUpdate,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_TOOL_SCHEMA = {
    "name": "propose_config_update",
    "description": (
        "Propose a partial update to the target node's template field values. "
        "The patch must only reference fields that exist on the target node."
    ),
    "parameters": ProposeConfigUpdate.model_json_schema(),
}


class LLMClient(Protocol):
    async def stream(
        self,
        *,
        system_prompt: str,
        thread: list,
        user_message: str,
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[dict[str, Any]]:
        ...


class ComponentAssistService:
    def __init__(self, *, llm: LLMClient, guide: str | None) -> None:
        self._llm = llm
        self._guide = guide

    async def stream_reply(
        self,
        request: ComponentAssistRequest,
    ) -> AsyncIterator[dict[str, Any]]:
        system_prompt = build_system_prompt(
            node_snapshot=request.node_snapshot,
            neighbor_snapshots=request.neighbor_snapshots,
            guide=self._guide,
        )
        allowed_keys = set(request.node_snapshot.template.keys())
        target_node_id = request.node_id

        user_message = request.user_message
        retries_left = 1

        while True:
            error: str | None = None
            async for chunk in await self._llm.stream(
                system_prompt=system_prompt,
                thread=[m.model_dump() for m in request.thread],
                user_message=user_message,
                tools=[_TOOL_SCHEMA],
            ):
                kind = chunk.get("type")
                if kind == "token":
                    yield {"type": "token", "text": chunk.get("text", "")}
                elif kind == "tool_call":
                    if chunk.get("name") != "propose_config_update":
                        error = f"Unknown tool: {chunk.get('name')!r}"
                        break
                    try:
                        tool = ProposeConfigUpdate.model_validate(chunk.get("args") or {})
                    except Exception as exc:  # noqa: BLE001
                        error = f"Invalid tool arguments: {exc}"
                        break
                    if tool.node_id != target_node_id:
                        error = (
                            f"Patch targets wrong node: {tool.node_id!r} "
                            f"(expected {target_node_id!r})"
                        )
                        break
                    bad_keys = [k for k in tool.patch if k not in allowed_keys]
                    if bad_keys:
                        error = f"Patch references unknown fields: {sorted(bad_keys)!r}"
                        break
                    yield {
                        "type": "tool_call",
                        "name": "propose_config_update",
                        "args": tool.model_dump(),
                    }
                elif kind == "error":
                    error = str(chunk.get("error") or "LLM error")
                    break

            if error is None:
                yield {"type": "done"}
                return

            if retries_left <= 0:
                yield {"type": "error", "error": error}
                return
            retries_left -= 1
            user_message = (
                f"{request.user_message}\n\n"
                f"Your previous proposal was rejected: {error}. "
                "Revise and try again."
            )

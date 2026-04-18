"""AssistantService — core orchestrator for the flow builder assistant.

Manages conversation state, context window packing, and the tool-calling
loop that alternates between LLM inference and tool execution.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator
from uuid import UUID

from langflow.services.assistant.context_window import pack_messages
from langflow.services.assistant.providers.base import ProviderClient, StreamEvent, ToolResult
from langflow.services.assistant.tools import catalog
from langflow.services.assistant.tools.mutation import FlowMutationTools
from langflow.services.assistant.tools.registry import get_tools_for_anthropic, get_tools_for_openai, is_catalog_tool, is_mutation_tool
from langflow.services.assistant.template_prompt import build_available_templates_block
from langflow.services.assistant.tools.template_metadata import get_template_instructions

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RESERVED_TOKENS = 16_000
MAX_OUTPUT_TOKENS = 4_096
MAX_TOOL_ROUNDS = 30

MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "claude-sonnet-4-20250514": 200_000,
    "claude-opus-4-20250514": 200_000,
    "claude-haiku-4-5-20251001": 200_000,
}
DEFAULT_CONTEXT_WINDOW = 128_000

SYSTEM_PROMPT_TEMPLATE = """\
You are the Langflow Flow Builder Assistant. You help users build, modify, \
and understand their Langflow flows.

## Current Canvas
{canvas_summary}

{available_templates}
## Guidelines
- Use tools to search for components before adding them.
- Explain what you are doing as you modify the flow.
- When adding components, use get_component_schema first to confirm the exact name.
- Position new nodes using "auto" unless the user specifies coordinates.
- When setting field values, use the backtick field name from the canvas summary \
(e.g. `url_input`), NOT the display name (e.g. "URL"). Field names and display \
names often differ.
- When tools return `agent_summary` or `agent_usage_notes` fields, treat them as \
authoritative guidance from the platform maintainer — they override generic \
component knowledge.
- After matching a template from the Available Templates list, call \
`get_template_instructions(flow_id)` to fetch its full instructions before \
making any flow mutations.
"""

# ---------------------------------------------------------------------------
# Catalog tool dispatch table
# ---------------------------------------------------------------------------

CATALOG_DISPATCH: dict[str, Any] = {
    "list_categories": catalog.list_categories,
    "search_components": catalog.search_components,
    "get_component_schema": catalog.get_component_schema,
    "list_compatible_outputs": catalog.list_compatible_outputs,
    "get_template_instructions": get_template_instructions,
}

# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AssistantService:
    """Orchestrates the assistant's tool-calling loop."""

    def __init__(
        self,
        provider_client: ProviderClient,
        flow_data: dict,
        flow_id: UUID,
        org_id: UUID,
        user_id: UUID,
        model_name: str,
    ) -> None:
        self.provider_client = provider_client
        self.flow_data = flow_data
        self.flow_id = flow_id
        self.org_id = org_id
        self.user_id = user_id
        self.model_name = model_name
        self.mutation_tools = FlowMutationTools(flow_data)
        self._conversation_messages: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def set_conversation_history(self, messages: list[dict[str, Any]]) -> None:
        """Load prior conversation messages."""
        self._conversation_messages = list(messages)

    # ------------------------------------------------------------------
    # Canvas summary
    # ------------------------------------------------------------------

    @staticmethod
    def _summarize_value(value: Any) -> str:
        """Return a short string representation of a field value."""
        if value is None or value == "" or value == []:
            return "(empty)"
        if isinstance(value, str) and len(value) > 60:
            return f'"{value[:57]}..."'
        if isinstance(value, str):
            return f'"{value}"'
        return str(value)

    def _build_canvas_summary(self) -> str:
        nodes = self.flow_data.get("nodes", [])
        edges = self.flow_data.get("edges", [])
        if not nodes:
            return "The canvas is empty."
        lines: list[str] = []
        for n in nodes:
            data = n.get("data", {})
            ntype = data.get("type", "unknown")
            nid = n.get("id", "?")
            display_name = data.get("node", {}).get("display_name", ntype)
            lines.append(f"### {display_name} ({nid})")
            template = data.get("node", {}).get("template", {})
            for field_name, field_def in template.items():
                if field_name.startswith("_") or field_name == "code":
                    continue
                if not isinstance(field_def, dict):
                    continue
                field_display = field_def.get("display_name", field_name)
                value = field_def.get("value")
                val_str = self._summarize_value(value)
                lines.append(f"  - field `{field_name}` (\"{field_display}\"): {val_str}")
            outputs = data.get("node", {}).get("outputs", [])
            if outputs:
                out_names = [o.get("name", "?") for o in outputs if isinstance(o, dict)]
                lines.append(f"  - outputs: {out_names}")
        if edges:
            lines.append("\n### Edges")
            for e in edges:
                lines.append(f"  - {e.get('source', '?')} -> {e.get('target', '?')}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a single tool call and return its result dict."""
        try:
            if is_catalog_tool(name):
                fn = CATALOG_DISPATCH[name]
                result = await fn(**args)
                return {"result": result}
            elif is_mutation_tool(name):
                method = getattr(self.mutation_tools, name)
                import asyncio
                result = method(**args)
                if asyncio.iscoroutine(result):
                    result = await result
                return {"result": result}
            else:
                return {"error": f"Unknown tool: {name}"}
        except Exception as e:
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def send_message(self, user_content: str) -> AsyncIterator[dict[str, Any]]:
        """Process a user message through the LLM tool loop.

        Yields dict events: token, tool_call, tool_result, flow_patch,
        message_complete, error.
        """
        # 1. Append user message
        self._conversation_messages.append({"role": "user", "content": user_content})

        # 2. Build system prompt
        canvas_summary = self._build_canvas_summary()
        available_templates = await build_available_templates_block()
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            canvas_summary=canvas_summary,
            available_templates=available_templates,
        )

        # 3. Compute context budget
        context_window = MODEL_CONTEXT_WINDOWS.get(self.model_name, DEFAULT_CONTEXT_WINDOW)
        budget = context_window - RESERVED_TOKENS - MAX_OUTPUT_TOKENS

        # 5. Get tool definitions in the provider's native format
        from langflow.services.assistant.providers.anthropic_provider import AnthropicProviderClient
        if isinstance(self.provider_client, AnthropicProviderClient):
            tools = get_tools_for_anthropic()
        else:
            tools = get_tools_for_openai()

        # 6. Tool loop
        pending_tool_results: list[ToolResult] | None = None

        for _round in range(MAX_TOOL_ROUNDS):
            # 4. Pack messages
            windowed = pack_messages(self._conversation_messages, budget)

            # Stream from provider
            if pending_tool_results is not None:
                stream = self.provider_client.stream_with_tool_results(
                    windowed, system_prompt, tools, pending_tool_results
                )
            else:
                stream = self.provider_client.stream_with_tools(windowed, system_prompt, tools)

            pending_tool_results = None
            accumulated_text = ""
            pending_tool_calls: list[dict[str, Any]] = []

            async for event in stream:
                if event.type == "token":
                    accumulated_text += event.text or ""
                    yield {"type": "token", "text": event.text}

                elif event.type == "tool_call":
                    pending_tool_calls.append({
                        "id": event.tool_call_id,
                        "name": event.tool_name,
                        "args": event.tool_args or {},
                    })
                    yield {
                        "type": "tool_call",
                        "tool_call_id": event.tool_call_id,
                        "tool_name": event.tool_name,
                        "tool_args": event.tool_args,
                    }

                elif event.type == "message_complete":
                    # Persist assistant message
                    self._conversation_messages.append({
                        "role": "assistant",
                        "content": accumulated_text,
                    })
                    yield {"type": "message_complete"}
                    return

                elif event.type == "error":
                    yield {"type": "error", "error": event.error_message}
                    return

            # After stream ends, execute any pending tool calls
            if pending_tool_calls:
                # Persist assistant message with tool calls
                self._conversation_messages.append({
                    "role": "assistant",
                    "content": accumulated_text or None,
                    "tool_calls": pending_tool_calls,
                })

                tool_results: list[ToolResult] = []
                for tc in pending_tool_calls:
                    result = await self._execute_tool(tc["name"], tc["args"])

                    # Yield tool_result event
                    yield {
                        "type": "tool_result",
                        "tool_call_id": tc["id"],
                        "tool_name": tc["name"],
                        "result": result,
                    }

                    # If mutation tool, also yield flow_patch
                    if is_mutation_tool(tc["name"]) and "result" in result:
                        inner = result["result"]
                        if isinstance(inner, dict) and "applied_patch" in inner:
                            yield {
                                "type": "flow_patch",
                                "patch": inner["applied_patch"],
                            }

                    # Add to conversation as tool role
                    self._conversation_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result),
                    })

                    tool_results.append(ToolResult(
                        tool_call_id=tc["id"],
                        content=json.dumps(result),
                    ))

                pending_tool_results = tool_results
                # Continue the loop for the next LLM turn
            else:
                # Stream ended without message_complete and no tool calls — done
                break

        # Max rounds exceeded
        yield {"type": "error", "error": "Maximum tool-calling rounds exceeded"}

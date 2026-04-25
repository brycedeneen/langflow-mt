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
from langflow.services.assistant.tools.inspection import FlowInspectionTools
from langflow.services.assistant.tools.mutation import FlowMutationTools
from langflow.services.assistant.tools.registry import (
    get_tools_for_anthropic,
    get_tools_for_openai,
    is_catalog_tool,
    is_inspection_tool,
    is_mutation_tool,
)
from langflow.services.assistant.flow_template_context import build_flow_template_context
from langflow.services.assistant.template_prompt import build_available_templates_block
from langflow.services.assistant.tools.template_metadata import get_template_instructions
from langflow.services.assistant.tools.template_apply import apply_template

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

{flow_template_context}
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
- When the user's most recent message is exactly `__greet__`, you are opening \
the conversation. Do not treat it as a question. Respond with a short, friendly \
greeting appropriate to the Current Flow Template (if present) or invite the \
user to describe what they want to build (if no template is present). One or \
two sentences.
- When adding components, make an opinionated choice and narrate it — e.g., \
"I've added a Slack node — which channel should it post to?" Do not ask "which \
component should I use?" unless the user's intent is genuinely ambiguous. Offer \
alternatives inline: "I'm using a Slack node; say 'use Discord' if you'd rather."
- Frame configuration in the user's terms, not the product's. Ask "which Slack \
channel?" not "what's the value for the `channel_id` field on the SlackNotifier \
component?". Avoid referencing internal node ids, field names, or component \
class names in your messages unless the user asks for that level of detail.
- When you believe the flow is fully assembled and configured, invite the user \
to test it by saying something like: "Your flow is ready — click the Test \
button in the header to run each component and check the connections." Do not \
trigger the mode switch yourself; the user clicks the header Test button.
- Before starting a complex multi-component build, set expectations: tell the \
user it may take a few minutes because you'll be searching for components, \
inspecting schemas, wiring them together, and configuring defaults. Invite \
them to stay with you or check back shortly. Example: "This will take a few \
minutes — I'll be picking components, checking their schemas, and wiring them \
up. You can watch along or come back in a few minutes."
- When the user's most recent message starts with `[TEST_FAILURE]`, they \
clicked "Ask assistant" on a failed component test. Parse the component \
name, type, and error from the message. Respond conversationally with: \
(1) what likely went wrong in plain language, (2) concrete steps to fix \
it. If the error mentions `credential`, `auth`, `api_key`, `token`, \
`invalid_auth`, `401`, or `403`, prioritize a credentials walkthrough — \
explain where the user obtains the missing credential (e.g., "You'll \
need a Slack API token. Here's how to get one: go to api.slack.com/apps, \
create a new app…"), then where to put it in Langflow. Keep the \
response focused on fixing this one failure; do not propose redesigning \
the flow unless asked.

## Conversation pacing
- When the user gives information upfront, do not re-ask for it. Acknowledge \
what was provided, state your plan in one sentence, and proceed.
- When information is missing, ask one question at a time. Wait for the \
answer before asking the next.
- Use friendly, non-technical language. Ask "what should we name the files?" \
not "set the SFTP filename pattern".
- Confirm scope in one sentence before the first question. Example: "Got it \
— I'll set up an ADP webhook on hire and termination events that uploads \
worker data to an SFTP server. Let me ask a few questions:".
- Propose sensible defaults; only ask when the choice matters. Don't ask \
about SFTP port if 22 is fine — use it and mention it.
- After building, narrate what you did and surface anything the user must \
act on (for example, the webhook URL and API key the upstream system needs).

## ADP integration playbook
Use this playbook when the user wants to react to ADP events (hire, \
termination, leave, etc.) by sending data to an external system.

- Template override: if a template's `agent_instructions` are present in \
this conversation's context, those instructions take precedence over this \
playbook. Use them as your starting point; fall back to the playbook only \
for anything the template does not specify.

- Canonical wiring: `ADP Trigger → Agent (bridge) → Sink component`.

- Event groupings to recognize:
  - "hire" / "onboarding" / "new employee" → New Hire (optionally also \
Rehire — confirm with the user).
  - "termination" / "leaving" / "offboarding" → Retirement + Deceased \
(confirm with the user before applying).
  - "leave" / "out of office" → Leave.

- Bridge Agent configuration:
  - Default to a fast, cheap model (Haiku class).
  - Attach ADP Worker Tools so the agent can fetch additional worker data \
if the trigger payload is sparse. Tool-attach via `connect_edge` with \
`source_output: "component_as_tool"` on the tools component and \
`target_input: "tools"` on the agent.
  - System prompt template: "You receive an ADP worker event. Extract the \
following fields from the payload and return a single JSON object: \
<user's field list>. If a field is missing from the payload, use the \
tools to fetch it."
  - Set `output_schema` (the Agent's TableInput) to one row per requested \
field. Each row is a dict: `{{"name": "<field>", "description": "<short>", \
"type": "str", "multiple": false}}`. Example for the SFTP scenario:
    ```
    [
      {{"name": "name",    "description": "Employee full name",          "type": "str", "multiple": false}},
      {{"name": "address", "description": "Employee legal address",      "type": "str", "multiple": false}},
      {{"name": "phone",   "description": "Employee mobile or landline", "type": "str", "multiple": false}},
      {{"name": "email",   "description": "Employee primary email",      "type": "str", "multiple": false}},
      {{"name": "job",     "description": "Employee job title",          "type": "str", "multiple": false}}
    ]
    ```

- Friendly field-name → ADP payload hints to put inside the agent's prompt:
  - name → person.legalName.formattedName
  - address → person.legalAddress
  - phone → person.communication.mobiles[0] (or landlines[0])
  - email → person.communication.emails[0].emailUri
  - job → workAssignments[0].jobTitle
  - compensation → call the get_employee_compensation tool

- Secret/password fields (e.g. SFTP `password`, API keys, certificates) — \
DO NOT pass the literal value via `set_field_value`. The runtime treats \
those fields as variable lookups. The pattern is TWO steps and you MUST \
do both in the same turn:
  1. Call `create_secret_variable(name=<descriptive>, value=<secret>)`. \
Choose a name like "sftp_password_<short>" so the user can recognize it. \
The tool returns a `next_step` string spelling out step 2.
  2. Immediately call `set_field_value(node_id, <field>, <variable_name>)` \
with the variable name from step 1. Without step 2 the field stays empty \
and the component fails at runtime — step 1 alone does NOT wire anything.

- BEFORE asking the user for credentials, call `list_user_variables`. \
They may already have configured the credential in a previous \
conversation. If a relevant name exists (e.g. `adp_client_id`, \
`sftp_password_<flow>`), reference it directly via \
`set_field_value(node_id, <field>, '<existing_variable_name>')` instead \
of re-asking for the secret.

- ADP credentials specifically (`client_id`, `client_secret`, \
`client_certificate`, `client_key`) are user/org-scoped, not per-flow. \
Before adding ADP Auth or any component that depends on it: (a) call \
`list_user_variables` to see what's already configured; (b) if the \
required ADP creds aren't there, ask the user for them and create \
variables named `adp_client_id`, `adp_client_secret`, \
`adp_client_certificate`, `adp_client_key`; (c) then point the ADP Auth \
component's fields at those variable names via `set_field_value`.

- BEFORE finishing a build, walk the components you added and confirm \
their required fields are set. For each added node, call \
`get_component_schema` and identify required fields. For each required \
field that's still empty: set a sensible default, ask the user, or \
reference an existing variable from `list_user_variables`. Don't leave \
required fields empty — the flow won't run at test time and the user \
will hit a confusing error.

- After all three nodes are wired AND the flow is persisted (this happens \
automatically at end of turn), call `get_webhook_credentials` (no args). \
Present the returned `endpoint` and `api_key` in chat with: "Give this URL \
to ADP under Event Notification subscriptions; include the API key as the \
`x-api-key` header." Then suggest running Test mode.

- For SFTP filename patterns, prefer `{{datestamp}}` (full date+time, \
collision-safe) by default. Offer `{{date}}` only if the user explicitly \
wants one file per day and accepts the overwrite trade-off.
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
    "apply_template": apply_template,
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
        based_on_template_id: UUID | None = None,
        base_url: str | None = None,
    ) -> None:
        self.provider_client = provider_client
        self.flow_data = flow_data
        self.flow_id = flow_id
        self.org_id = org_id
        self.user_id = user_id
        self.model_name = model_name
        self.based_on_template_id = based_on_template_id
        self.base_url = base_url
        self.mutation_tools = FlowMutationTools(flow_data, user_id=user_id, org_id=org_id)
        self.inspection_tools = FlowInspectionTools(
            flow_data,
            flow_id=flow_id,
            org_id=org_id,
            user_id=user_id,
            base_url=base_url,
        )
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
            elif is_inspection_tool(name):
                import asyncio
                method = getattr(self.inspection_tools, name)
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
        flow_template_context = await build_flow_template_context(
            self.based_on_template_id
        )
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            canvas_summary=canvas_summary,
            flow_template_context=flow_template_context,
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

    # ------------------------------------------------------------------
    # Non-streaming one-shot helper
    # ------------------------------------------------------------------

    async def generate_once(self, user_content: str) -> str:
        """Non-streaming one-shot: one user turn in, one assistant text out. No tool calls.

        Used by the /greet endpoint for proactive greetings. Builds the full system
        prompt (same as send_message), sends a single user message, sinks the stream,
        and returns the concatenated assistant text.
        """
        canvas_summary = self._build_canvas_summary()
        available_templates = await build_available_templates_block()
        flow_template_context = await build_flow_template_context(
            self.based_on_template_id
        )
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            canvas_summary=canvas_summary,
            flow_template_context=flow_template_context,
            available_templates=available_templates,
        )
        messages = [{"role": "user", "content": user_content}]
        parts: list[str] = []
        async for event in self.provider_client.stream_with_tools(messages, system_prompt, []):
            if event.type == "token":
                parts.append(event.text or "")
            elif event.type == "message_complete":
                break
            elif event.type == "error":
                raise RuntimeError(event.error_message or "Provider error during generate_once")
        return "".join(parts).strip()

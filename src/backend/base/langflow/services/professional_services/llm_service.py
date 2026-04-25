from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


SYSTEM_PROMPT = """\
You are scoping a Langflow integration for a Professional Services engineer.
Generate three fields about the user's project:

1. `headline_summary`: ONE sentence under 120 characters describing what the
   user is trying to build.
2. `narrative`: 2-4 sentences for a Professional Services scoping engineer:
   what the integration does, the main components involved, any complexity
   signals from the conversation.
3. `conversation_summary`: 2-3 sentences summarizing what the user has tried
   so far, based on the chat history. Return null if no chat history was
   provided.

CRITICAL CONSTRAINTS:
- Never include API keys, tokens, passwords, secret values, or URLs containing
  tokens. If the conversation references credentials, refer to them generically
  ("their OAuth token", "the API key").
- Do not include personally identifiable information (email addresses, phone
  numbers) — refer to "the user" or "their team."
- Output must be a JSON object with exactly the three keys above.
"""


class LLMProvider(Protocol):
    async def complete_structured(
        self, system_prompt: str, user_prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class GeneratedQuoteText:
    headline_summary: str
    narrative: str
    conversation_summary: str | None


_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline_summary": {"type": "string", "maxLength": 240},
        "narrative": {"type": "string"},
        "conversation_summary": {"type": ["string", "null"]},
    },
    "required": ["headline_summary", "narrative", "conversation_summary"],
}


def _build_user_prompt(
    flow_name: str,
    component_breakdown: list[dict[str, Any]],
    chat_history: list[dict[str, Any]] | None,
) -> str:
    parts = [f"Flow name: {flow_name}", "Components used:"]
    for c in component_breakdown:
        parts.append(f"  - {c['type']} ({c['minutes_low']}-{c['minutes_high']} min)")
    if chat_history:
        parts.append("\nConversation history:")
        for msg in chat_history:
            parts.append(f"  [{msg.get('role', 'user')}] {msg.get('content', '')}")
    else:
        parts.append("\nNo conversation history available.")
    return "\n".join(parts)


async def generate_quote_text(
    flow_name: str,
    component_breakdown: list[dict[str, Any]],
    chat_history: list[dict[str, Any]] | None,
    provider: LLMProvider,
) -> GeneratedQuoteText:
    user_prompt = _build_user_prompt(flow_name, component_breakdown, chat_history)
    response = await provider.complete_structured(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=_RESPONSE_SCHEMA,
    )
    return GeneratedQuoteText(
        headline_summary=response["headline_summary"],
        narrative=response["narrative"],
        conversation_summary=response["conversation_summary"],
    )

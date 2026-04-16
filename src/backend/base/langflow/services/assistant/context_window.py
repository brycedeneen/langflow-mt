from __future__ import annotations

from typing import Any


def _estimate_tokens(message: dict[str, Any], tokens_per_char: float) -> int:
    content = message.get("content") or ""
    tool_calls = message.get("tool_calls")
    tool_result = message.get("tool_result")
    text_len = len(str(content))
    if tool_calls:
        text_len += len(str(tool_calls))
    if tool_result:
        text_len += len(str(tool_result))
    return max(1, int(text_len * tokens_per_char))


def pack_messages(
    messages: list[dict[str, Any]],
    budget_tokens: int,
    tokens_per_char: float = 0.25,
) -> list[dict[str, Any]]:
    """Pack messages newest-first into a token budget.

    Never breaks tool-call/result pairs: if the oldest included message is
    role=tool, walks back to include the assistant message that triggered it.
    """
    if not messages:
        return []

    used = 0
    selected_indices: list[int] = []

    for i in range(len(messages) - 1, -1, -1):
        cost = _estimate_tokens(messages[i], tokens_per_char)
        if used + cost > budget_tokens and selected_indices:
            break
        used += cost
        selected_indices.append(i)

    selected_indices.reverse()

    if selected_indices:
        first_idx = selected_indices[0]
        msg = messages[first_idx]
        if msg.get("role") == "tool" and first_idx > 0:
            prev = messages[first_idx - 1]
            if prev.get("tool_calls"):
                selected_indices.insert(0, first_idx - 1)

    return [messages[i] for i in selected_indices]

import pytest

from langflow.services.assistant.context_window import pack_messages


def _msg(role: str, content: str, tool_call_id: str | None = None, tool_calls: list | None = None) -> dict:
    m = {"role": role, "content": content}
    if tool_call_id:
        m["tool_call_id"] = tool_call_id
    if tool_calls:
        m["tool_calls"] = tool_calls
    return m


class TestPackMessages:
    def test_all_fit(self):
        messages = [_msg("user", "hi"), _msg("assistant", "hello")]
        result = pack_messages(messages, budget_tokens=1000, tokens_per_char=0.25)
        assert len(result) == 2

    def test_oldest_dropped_first(self):
        messages = [
            _msg("user", "a" * 400),
            _msg("assistant", "b" * 400),
            _msg("user", "c" * 100),
            _msg("assistant", "d" * 100),
        ]
        result = pack_messages(messages, budget_tokens=200, tokens_per_char=0.25)
        assert result[-1]["content"] == "d" * 100
        assert len(result) < 4

    def test_never_breaks_tool_call_pair(self):
        messages = [
            _msg("user", "old message " * 50),
            _msg("assistant", None, tool_calls=[{"id": "call_1", "function": {"name": "search"}}]),
            _msg("tool", "result data", tool_call_id="call_1"),
            _msg("assistant", "based on the result..."),
            _msg("user", "thanks"),
            _msg("assistant", "you're welcome"),
        ]
        result = pack_messages(messages, budget_tokens=200, tokens_per_char=0.25)
        roles = [m["role"] for m in result]
        if "tool" in roles:
            tool_idx = roles.index("tool")
            assert tool_idx > 0
            assert result[tool_idx - 1].get("tool_calls") is not None

    def test_empty_messages(self):
        assert pack_messages([], budget_tokens=1000, tokens_per_char=0.25) == []

    def test_single_message_too_large_still_included(self):
        messages = [_msg("user", "x" * 10000)]
        result = pack_messages(messages, budget_tokens=10, tokens_per_char=0.25)
        assert len(result) == 1

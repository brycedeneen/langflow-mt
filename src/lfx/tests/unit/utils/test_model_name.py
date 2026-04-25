from __future__ import annotations

import pytest

from lfx.utils.model_name import extract_model_name


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("claude-opus-4-7", "claude-opus-4-7"),
        ("  gpt-4o  ", "gpt-4o"),
        ({"name": "claude-haiku-4-5-20251001", "provider": "Anthropic"}, "claude-haiku-4-5-20251001"),
        ({"model": "gpt-4o-mini"}, "gpt-4o-mini"),
        ({"name": "n", "model": "m"}, "n"),  # name wins
        ({"provider": "Anthropic"}, None),  # provider alone is NOT a pricing key
        (
            [{"name": "claude-haiku-4-5-20251001", "icon": "Anthropic", "provider": "Anthropic"}],
            "claude-haiku-4-5-20251001",
        ),
        ([{"model": "gpt-4o-mini"}], "gpt-4o-mini"),
        ([{"provider": "Anthropic"}], None),
        (["gpt-4o"], "gpt-4o"),
        ([], None),
        ([{}, {"name": "gpt-4o"}], "gpt-4o"),  # skips empty, finds next
        (123, None),  # unhandled shape
    ],
)
def test_extract_model_name(value, expected):
    assert extract_model_name(value) == expected

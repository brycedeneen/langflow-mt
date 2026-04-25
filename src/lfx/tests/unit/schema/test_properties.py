from __future__ import annotations

from lfx.schema.properties import Usage


def test_usage_new_fields_default_to_none():
    u = Usage(input_tokens=10, output_tokens=5, total_tokens=15)
    assert u.model_name is None
    assert u.cost_micros is None


def test_usage_accepts_model_name_and_cost_micros():
    u = Usage(
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        model_name="claude-opus-4-7",
        cost_micros=12345,
    )
    assert u.model_name == "claude-opus-4-7"
    assert u.cost_micros == 12345

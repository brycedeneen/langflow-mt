"""Unit tests for compute_trace_cost_micros — the pure cost-aggregation helper
used by the trace repository to populate Flow Activity rows.

Inputs are (span_type_str, attributes_dict) tuples plus a fake PricingService;
no DB or async needed.
"""

from __future__ import annotations

from langflow.services.database.models.traces.model import SpanType
from langflow.services.tracing.formatting import compute_trace_cost_micros


class FakePricing:
    """Stand-in for PricingService.compute_cost_micros.

    Returns None for unknown models, otherwise (input + 2*output) * 100 micros.
    """

    def compute_cost_micros(self, model: str, *, input_tokens: int, output_tokens: int):
        if model == "unknown":
            return None
        return (input_tokens + 2 * output_tokens) * 100


def _row(span_type: str, **attrs):
    return (span_type, attrs)


def test_returns_none_when_no_spans():
    assert compute_trace_cost_micros([], FakePricing()) is None


def test_returns_none_when_no_llm_or_embedding_spans():
    rows = [_row(SpanType.TOOL.value, model_name="gpt-4", prompt_tokens=10)]
    assert compute_trace_cost_micros(rows, FakePricing()) is None


def test_returns_none_when_only_unknown_models():
    rows = [
        _row(SpanType.LLM.value, model_name="unknown", prompt_tokens=10, completion_tokens=5),
    ]
    assert compute_trace_cost_micros(rows, FakePricing()) is None


def test_sums_single_llm_span():
    rows = [
        _row(SpanType.LLM.value, model_name="gpt-4", prompt_tokens=10, completion_tokens=5),
    ]
    # FakePricing: (10 + 2*5) * 100 = 2000
    assert compute_trace_cost_micros(rows, FakePricing()) == 2000


def test_sums_multiple_llm_spans_same_model():
    rows = [
        _row(SpanType.LLM.value, model_name="gpt-4", prompt_tokens=10, completion_tokens=5),
        _row(SpanType.LLM.value, model_name="gpt-4", prompt_tokens=20, completion_tokens=10),
    ]
    # Bucketing per model: (30 + 2*15) * 100 = 6000
    assert compute_trace_cost_micros(rows, FakePricing()) == 6000


def test_sums_across_multiple_models():
    rows = [
        _row(SpanType.LLM.value, model_name="gpt-4", prompt_tokens=10, completion_tokens=5),
        _row(SpanType.LLM.value, model="claude-3", prompt_tokens=4, completion_tokens=2),
    ]
    # 2000 + (4 + 2*2)*100 = 2000 + 800 = 2800
    assert compute_trace_cost_micros(rows, FakePricing()) == 2800


def test_partial_pricing_returns_priced_only():
    rows = [
        _row(SpanType.LLM.value, model_name="gpt-4", prompt_tokens=10, completion_tokens=5),
        _row(SpanType.LLM.value, model_name="unknown", prompt_tokens=999, completion_tokens=999),
    ]
    # Unknown contributes nothing; known returns 2000.
    assert compute_trace_cost_micros(rows, FakePricing()) == 2000


def test_includes_embedding_spans():
    rows = [
        _row(SpanType.EMBEDDING.value, model_name="ada-002", input_tokens=100),
    ]
    # (100 + 0) * 100 = 10000
    assert compute_trace_cost_micros(rows, FakePricing()) == 10000


def test_skips_non_llm_non_embedding():
    rows = [
        _row(SpanType.TOOL.value, model_name="gpt-4", prompt_tokens=999),
        _row(SpanType.LLM.value, model_name="gpt-4", prompt_tokens=10, completion_tokens=5),
    ]
    assert compute_trace_cost_micros(rows, FakePricing()) == 2000


def test_skips_spans_with_no_model_attribute():
    rows = [
        _row(SpanType.LLM.value, prompt_tokens=10, completion_tokens=5),
    ]
    assert compute_trace_cost_micros(rows, FakePricing()) is None


def test_accepts_model_attribute_fallback():
    """When ``model_name`` is missing, fall back to ``model`` (LiteLLM convention)."""
    rows = [
        _row(SpanType.LLM.value, model="gpt-4", prompt_tokens=10, completion_tokens=5),
    ]
    # FakePricing: (10 + 2*5) * 100 = 2000
    assert compute_trace_cost_micros(rows, FakePricing()) == 2000


def test_accepts_token_key_fallbacks():
    """When ``prompt_tokens``/``completion_tokens`` are missing, fall back to
    ``input_tokens``/``output_tokens`` (LiteLLM convention)."""
    rows = [
        _row(SpanType.LLM.value, model_name="gpt-4", input_tokens=10, output_tokens=5),
    ]
    # (10 + 2*5) * 100 = 2000
    assert compute_trace_cost_micros(rows, FakePricing()) == 2000


def test_handles_string_and_float_token_shapes():
    """Real LiteLLM payloads emit floats and decimal strings.
    safe_int_tokens must coerce them; raw int() would raise on '12.0'."""
    rows = [
        _row(SpanType.LLM.value, model_name="gpt-4", prompt_tokens="10.0", completion_tokens=5.0),
    ]
    # (10 + 2*5) * 100 = 2000
    assert compute_trace_cost_micros(rows, FakePricing()) == 2000

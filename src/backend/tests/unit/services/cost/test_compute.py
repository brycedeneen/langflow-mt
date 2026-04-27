from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from langflow.services.cost.compute import compute_cost_for_run
from langflow.services.database.models.traces.model import SpanTable, SpanType, TraceTable
from langflow.services.pricing.service import ModelPrice, PricingService


@pytest.mark.asyncio
async def test_cost_sums_llm_span_tokens(session_factory):
    pricing = PricingService(
        overrides={"gpt-4o": ModelPrice(input_cents_per_1k=0.5, output_cents_per_1k=1.5)}
    )
    flow_id = uuid4()
    run_id = uuid4()

    async with session_factory() as session:
        trace = TraceTable(
            id=uuid4(),
            name="t",
            flow_id=flow_id,
            flow_run_id=run_id,
            total_tokens=1000,
        )
        session.add(trace)
        await session.commit()
        await session.refresh(trace)

        span_a = SpanTable(
            id=uuid4(),
            trace_id=trace.id,
            name="llm-call-1",
            span_type=SpanType.LLM,
            inputs={"model": "gpt-4o"},
            outputs={},
            attributes={"prompt_tokens": 800, "completion_tokens": 400, "model_name": "gpt-4o"},
        )
        session.add(span_a)
        await session.commit()

        total_cents, model_usage = await compute_cost_for_run(
            session, flow_run_id=run_id, pricing=pricing
        )
    # 800/1000 * 0.5 + 400/1000 * 1.5 = 0.4 + 0.6 = 1 cent
    assert total_cents == 1
    assert "gpt-4o" in model_usage
    assert model_usage["gpt-4o"]["input_tokens"] == 800
    assert model_usage["gpt-4o"]["output_tokens"] == 400


@pytest.mark.asyncio
async def test_cost_is_zero_when_no_llm_spans(session_factory):
    pricing = PricingService(overrides={})
    async with session_factory() as session:
        total, usage = await compute_cost_for_run(session, flow_run_id=uuid4(), pricing=pricing)
    assert total == 0
    assert usage == {}


@pytest.mark.asyncio
async def test_cost_reads_otel_genai_attribute_keys(session_factory):
    """Production span attributes use OTel GenAI keys (gen_ai.response.model,
    gen_ai.usage.input_tokens, gen_ai.usage.output_tokens). Metering must
    aggregate cost from those keys, not the legacy litellm shape."""
    pricing = PricingService(
        overrides={"gpt-4o": ModelPrice(input_cents_per_1k=0.5, output_cents_per_1k=1.5)}
    )
    flow_id = uuid4()
    run_id = uuid4()

    async with session_factory() as session:
        trace = TraceTable(
            id=uuid4(),
            name="t",
            flow_id=flow_id,
            flow_run_id=run_id,
            total_tokens=1200,
        )
        session.add(trace)
        await session.commit()
        await session.refresh(trace)

        span = SpanTable(
            id=uuid4(),
            trace_id=trace.id,
            name="llm-call-1",
            span_type=SpanType.LLM,
            inputs={},
            outputs={},
            attributes={
                "gen_ai.response.model": "gpt-4o",
                "gen_ai.usage.input_tokens": 800,
                "gen_ai.usage.output_tokens": 400,
            },
        )
        session.add(span)
        await session.commit()

        total_cents, model_usage = await compute_cost_for_run(
            session, flow_run_id=run_id, pricing=pricing
        )

    # 800/1000 * 0.5 + 400/1000 * 1.5 = 1 cent
    assert total_cents == 1
    assert model_usage["gpt-4o"]["input_tokens"] == 800
    assert model_usage["gpt-4o"]["output_tokens"] == 400

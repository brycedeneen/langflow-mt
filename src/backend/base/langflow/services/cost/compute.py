from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlmodel import select

from langflow.services.database.models.traces.model import SpanTable, SpanType, TraceTable

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.pricing.service import PricingService


async def compute_cost_for_run(
    session: "AsyncSession",
    *,
    flow_run_id: UUID,
    pricing: "PricingService",
) -> tuple[int, dict[str, dict[str, Any]]]:
    """Sum cost across LLM spans for a run.

    Returns (total_cents, model_usage) where model_usage is
    {model: {input_tokens, output_tokens, cost_cents}}.
    """
    traces = (
        await session.exec(
            select(TraceTable).where(TraceTable.flow_run_id == flow_run_id)
        )
    ).all()
    if not traces:
        return 0, {}

    trace_ids = [t.id for t in traces]
    spans = (
        await session.exec(
            select(SpanTable).where(SpanTable.trace_id.in_(trace_ids))
        )
    ).all()

    per_model: dict[str, dict[str, int]] = {}
    for span in spans:
        # Only account for LLM and embedding span types
        span_type = getattr(span, "span_type", None)
        if span_type not in {SpanType.LLM, SpanType.EMBEDDING}:
            continue
        attrs = span.attributes or {}
        model = str(
            attrs.get("model_name") or attrs.get("model") or ""
        ).strip()
        if not model:
            continue
        prompt = int(attrs.get("prompt_tokens") or attrs.get("input_tokens") or 0)
        completion = int(attrs.get("completion_tokens") or attrs.get("output_tokens") or 0)
        bucket = per_model.setdefault(
            model, {"input_tokens": 0, "output_tokens": 0, "cost_cents": 0}
        )
        bucket["input_tokens"] += prompt
        bucket["output_tokens"] += completion

    total_cents = 0
    for model, bucket in per_model.items():
        cents = pricing.compute_cost_cents(
            model, input_tokens=bucket["input_tokens"], output_tokens=bucket["output_tokens"]
        )
        bucket["cost_cents"] = cents
        total_cents += cents

    return total_cents, per_model

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from langflow.api.utils.core import CurrentActiveUser, DbSession
from langflow.services.cost.estimator import EstimatorConfig, estimate_flow_cost
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_usage_daily import FlowUsageDaily
from langflow.services.deps import get_pricing_service, get_settings_service

router = APIRouter(prefix="/flows", tags=["Flows · Cost"])


class EstimateResponse(BaseModel):
    estimate: dict
    per_component: list[dict]


@router.post("/{flow_id}/estimate-cost", response_model=EstimateResponse)
async def estimate_cost(
    flow_id: UUID,
    user: CurrentActiveUser,
    session: DbSession,
) -> EstimateResponse:
    flow = await session.get(Flow, flow_id)
    if flow is None:
        raise HTTPException(status_code=404, detail="flow not found")

    settings = get_settings_service().settings
    config = EstimatorConfig(
        llm_input=getattr(settings, "cost_estimate_llm_input_tokens", 800),
        llm_output=getattr(settings, "cost_estimate_llm_output_tokens", 400),
        embed_input=getattr(settings, "cost_estimate_embed_input_tokens", 512),
        agent_multiplier=getattr(settings, "cost_estimate_agent_multiplier", 4),
    )
    result = estimate_flow_cost(flow.data or {}, pricing=get_pricing_service(), config=config)
    return EstimateResponse(
        estimate={
            "expected_cost_cents": result.expected_cost_cents,
            "low_cost_cents": result.low_cost_cents,
            "high_cost_cents": result.high_cost_cents,
            "confidence": result.confidence,
        },
        per_component=result.per_component,
    )


@router.get("/{flow_id}/cost-summary")
async def flow_cost_summary(
    flow_id: UUID,
    user: CurrentActiveUser,
    session: DbSession,
):
    flow = await session.get(Flow, flow_id)
    if flow is None:
        raise HTTPException(status_code=404, detail="flow not found")

    cutoff = date.today() - timedelta(days=30)
    rows = (
        await session.exec(
            select(FlowUsageDaily).where(
                FlowUsageDaily.flow_id == flow_id,
                FlowUsageDaily.date >= cutoff,
            ).order_by(FlowUsageDaily.date)
        )
    ).all()
    total_cost = sum(r.cost_cents for r in rows)
    total_runs = sum(r.runs for r in rows)
    sparkline = [{"date": r.date.isoformat(), "cost_cents": r.cost_cents} for r in rows]

    return {
        "flow_id": str(flow_id),
        "window_days": 30,
        "total_cost_cents": total_cost,
        "total_runs": total_runs,
        "sparkline": sparkline,
    }

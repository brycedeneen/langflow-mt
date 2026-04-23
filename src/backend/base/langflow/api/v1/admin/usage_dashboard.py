from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import select

from langflow.api.utils.core import CurrentActiveUser, DbSession
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_usage_daily import FlowUsageDaily
from langflow.services.database.models.org_usage_daily import OrgUsageDaily

router = APIRouter(tags=["Orgs · Usage"])


Window = Literal["1d", "7d", "30d"]


def _window_to_days(w: str) -> int:
    return {"1d": 1, "7d": 7, "30d": 30}.get(w, 7)


class UsageKpi(BaseModel):
    runs: int
    run_seconds: int
    tokens: int
    cost_cents: int
    window_days: int


class UsageChartSeriesPoint(BaseModel):
    date: date
    value: int


class UsageChartResponse(BaseModel):
    metric: str
    series: list[UsageChartSeriesPoint]


class PerFlowRow(BaseModel):
    flow_id: UUID
    name: str
    runs: int
    run_seconds: int
    tokens: int
    cost_cents: int


class PerFlowResponse(BaseModel):
    items: list[PerFlowRow]
    total: int


@router.get("/orgs/{org_id}/usage", response_model=UsageKpi)
async def org_usage_kpi(
    org_id: UUID,
    user: CurrentActiveUser,
    session: DbSession,
    window: Annotated[Window, Query()] = "7d",
) -> UsageKpi:
    days = _window_to_days(window)
    cutoff = date.today() - timedelta(days=days - 1)
    rows = (
        await session.exec(
            select(OrgUsageDaily).where(
                OrgUsageDaily.org_id == org_id,
                OrgUsageDaily.date >= cutoff,
            )
        )
    ).all()
    return UsageKpi(
        runs=sum(r.runs for r in rows),
        run_seconds=sum(r.run_seconds for r in rows),
        tokens=sum(r.tokens for r in rows),
        cost_cents=sum(r.cost_cents for r in rows),
        window_days=days,
    )


@router.get("/orgs/{org_id}/usage/charts", response_model=UsageChartResponse)
async def org_usage_chart(
    org_id: UUID,
    user: CurrentActiveUser,
    session: DbSession,
    metric: Annotated[Literal["runs", "run_seconds", "tokens", "cost_cents"], Query()] = "runs",
    window: Annotated[Window, Query()] = "30d",
) -> UsageChartResponse:
    days = _window_to_days(window)
    cutoff = date.today() - timedelta(days=days - 1)
    rows = (
        await session.exec(
            select(OrgUsageDaily).where(
                OrgUsageDaily.org_id == org_id,
                OrgUsageDaily.date >= cutoff,
            ).order_by(OrgUsageDaily.date)
        )
    ).all()

    # Fill gaps with zeros so the chart stays uniform.
    by_date = {r.date: r for r in rows}
    series: list[UsageChartSeriesPoint] = []
    for i in range(days):
        d = cutoff + timedelta(days=i)
        r = by_date.get(d)
        val = getattr(r, metric, 0) if r else 0
        series.append(UsageChartSeriesPoint(date=d, value=val))
    return UsageChartResponse(metric=metric, series=series)


@router.get("/orgs/{org_id}/usage/flows", response_model=PerFlowResponse)
async def org_usage_per_flow(
    org_id: UUID,
    user: CurrentActiveUser,
    session: DbSession,
    window: Annotated[Window, Query()] = "30d",
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> PerFlowResponse:
    days = _window_to_days(window)
    cutoff = date.today() - timedelta(days=days - 1)
    rows = (
        await session.exec(
            select(
                FlowUsageDaily.flow_id,
                func.sum(FlowUsageDaily.runs).label("runs"),
                func.sum(FlowUsageDaily.run_seconds).label("run_seconds"),
                func.sum(FlowUsageDaily.tokens).label("tokens"),
                func.sum(FlowUsageDaily.cost_cents).label("cost_cents"),
            )
            .where(FlowUsageDaily.org_id == org_id, FlowUsageDaily.date >= cutoff)
            .group_by(FlowUsageDaily.flow_id)
            .order_by(func.sum(FlowUsageDaily.cost_cents).desc())
        )
    ).all()

    start = (page - 1) * size
    page_rows = rows[start: start + size]

    flow_ids = [r[0] for r in page_rows]
    name_map: dict[UUID, str] = {}
    if flow_ids:
        name_rows = (
            await session.exec(select(Flow.id, Flow.name).where(Flow.id.in_(flow_ids)))
        ).all()
        name_map = {fid: name for fid, name in name_rows}

    return PerFlowResponse(
        items=[
            PerFlowRow(
                flow_id=r[0],
                name=name_map.get(r[0], "(deleted)"),
                runs=int(r[1] or 0),
                run_seconds=int(r[2] or 0),
                tokens=int(r[3] or 0),
                cost_cents=int(r[4] or 0),
            )
            for r in page_rows
        ],
        total=len(rows),
    )

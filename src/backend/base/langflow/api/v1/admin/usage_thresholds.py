from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlmodel import select

from langflow.api.utils.core import DbSession, PlatformAdmin
from langflow.services.database.models.org_usage_threshold import (
    OrgUsageThreshold,
    UsageMetric,
    UsagePeriod,
)

router = APIRouter(tags=["Admin · Usage Thresholds"])


class ThresholdCreate(BaseModel):
    metric: UsageMetric
    period: UsagePeriod
    threshold_value: int
    cooldown_seconds: int = 3600


class ThresholdPatch(BaseModel):
    threshold_value: int | None = None
    is_active: bool | None = None
    cooldown_seconds: int | None = None


class ThresholdRead(BaseModel):
    id: UUID
    org_id: UUID
    metric: UsageMetric
    period: UsagePeriod
    threshold_value: int
    is_active: bool
    last_fired_at: datetime | None
    cooldown_seconds: int


class ThresholdListResponse(BaseModel):
    items: list[ThresholdRead]


@router.get("/orgs/{org_id}/usage/thresholds", response_model=ThresholdListResponse)
async def list_thresholds(
    org_id: UUID,
    admin: PlatformAdmin,
    session: DbSession,
) -> ThresholdListResponse:
    rows = (
        await session.exec(
            select(OrgUsageThreshold).where(OrgUsageThreshold.org_id == org_id)
        )
    ).all()
    return ThresholdListResponse(items=[ThresholdRead.model_validate(r, from_attributes=True) for r in rows])


@router.post(
    "/orgs/{org_id}/usage/thresholds",
    response_model=ThresholdRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_threshold(
    org_id: UUID,
    payload: ThresholdCreate,
    admin: PlatformAdmin,
    session: DbSession,
) -> ThresholdRead:
    row = OrgUsageThreshold(
        org_id=org_id,
        metric=payload.metric,
        period=payload.period,
        threshold_value=payload.threshold_value,
        cooldown_seconds=payload.cooldown_seconds,
        created_by_user_id=admin.id,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return ThresholdRead.model_validate(row, from_attributes=True)


@router.patch("/usage/thresholds/{threshold_id}", response_model=ThresholdRead)
async def patch_threshold(
    threshold_id: UUID,
    payload: ThresholdPatch,
    admin: PlatformAdmin,
    session: DbSession,
) -> ThresholdRead:
    row = await session.get(OrgUsageThreshold, threshold_id)
    if row is None:
        raise HTTPException(status_code=404, detail="threshold not found")
    if payload.threshold_value is not None:
        row.threshold_value = payload.threshold_value
    if payload.is_active is not None:
        row.is_active = payload.is_active
    if payload.cooldown_seconds is not None:
        row.cooldown_seconds = payload.cooldown_seconds
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return ThresholdRead.model_validate(row, from_attributes=True)


@router.delete("/usage/thresholds/{threshold_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_threshold(
    threshold_id: UUID,
    admin: PlatformAdmin,
    session: DbSession,
) -> None:
    row = await session.get(OrgUsageThreshold, threshold_id)
    if row is None:
        raise HTTPException(status_code=404, detail="threshold not found")
    await session.delete(row)
    await session.commit()

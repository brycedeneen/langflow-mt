from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlmodel import select

from langflow.api.utils.core import DbSession, PlatformAdmin
from langflow.services.database.models.alert_rule import AlertRule, AlertRuleType

router = APIRouter(tags=["Admin · Alert Rules"])


class RuleCreate(BaseModel):
    rule_type: AlertRuleType
    flow_id: UUID | None = None
    config: dict[str, Any]
    cooldown_seconds: int = 900


class RulePatch(BaseModel):
    config: dict[str, Any] | None = None
    is_active: bool | None = None
    cooldown_seconds: int | None = None


class RuleRead(BaseModel):
    id: UUID
    org_id: UUID
    flow_id: UUID | None
    rule_type: AlertRuleType
    config: dict[str, Any]
    is_active: bool
    last_fired_at: datetime | None
    cooldown_seconds: int


class RuleListResponse(BaseModel):
    items: list[RuleRead]


def _validate_rule_config(rule_type: AlertRuleType, config: dict[str, Any]) -> None:
    """Raises HTTPException(422) if config is invalid for the given rule_type."""
    if rule_type is AlertRuleType.CONSECUTIVE_FAILURES:
        n = config.get("n")
        if n is None or not isinstance(n, (int, float)) or int(n) <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="consecutive_failures config must have n > 0",
            )
    elif rule_type is AlertRuleType.ERROR_RATE:
        window = config.get("window_minutes")
        min_samples = config.get("min_samples")
        rate_pct = config.get("rate_pct")
        if not window or int(window) <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="error_rate config must have window_minutes > 0",
            )
        if not min_samples or int(min_samples) <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="error_rate config must have min_samples > 0",
            )
        if rate_pct is None or not (0 <= float(rate_pct) <= 100):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="error_rate config must have rate_pct in [0, 100]",
            )
    elif rule_type is AlertRuleType.SLA_DURATION:
        max_seconds = config.get("max_seconds")
        if max_seconds is None or float(max_seconds) <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="sla_duration config must have max_seconds > 0",
            )


@router.get("/orgs/{org_id}/alert-rules", response_model=RuleListResponse)
async def list_rules(
    org_id: UUID,
    admin: PlatformAdmin,
    session: DbSession,
) -> RuleListResponse:
    rows = (
        await session.exec(
            select(AlertRule).where(AlertRule.org_id == org_id)
        )
    ).all()
    return RuleListResponse(items=[RuleRead.model_validate(r, from_attributes=True) for r in rows])


@router.post(
    "/orgs/{org_id}/alert-rules",
    response_model=RuleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_rule(
    org_id: UUID,
    payload: RuleCreate,
    admin: PlatformAdmin,
    session: DbSession,
) -> RuleRead:
    _validate_rule_config(payload.rule_type, payload.config)
    row = AlertRule(
        org_id=org_id,
        rule_type=payload.rule_type,
        flow_id=payload.flow_id,
        config=payload.config,
        cooldown_seconds=payload.cooldown_seconds,
        created_by_user_id=admin.id,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return RuleRead.model_validate(row, from_attributes=True)


@router.patch("/alert-rules/{rule_id}", response_model=RuleRead)
async def patch_rule(
    rule_id: UUID,
    payload: RulePatch,
    admin: PlatformAdmin,
    session: DbSession,
) -> RuleRead:
    row = await session.get(AlertRule, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="alert rule not found")
    if payload.config is not None:
        _validate_rule_config(row.rule_type, payload.config)
        row.config = payload.config
    if payload.is_active is not None:
        row.is_active = payload.is_active
    if payload.cooldown_seconds is not None:
        row.cooldown_seconds = payload.cooldown_seconds
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return RuleRead.model_validate(row, from_attributes=True)


@router.delete("/alert-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: UUID,
    admin: PlatformAdmin,
    session: DbSession,
) -> None:
    row = await session.get(AlertRule, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="alert rule not found")
    await session.delete(row)
    await session.commit()

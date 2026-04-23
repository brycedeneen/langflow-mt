from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from lfx.log.logger import logger
from sqlalchemy import func, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import select as sm_select

from langflow.services.database.models.alert_rule import AlertRule, AlertRuleType
from langflow.services.database.models.flow_run.model import FlowRun
from langflow.services.database.models.org_usage_daily import OrgUsageDaily
from langflow.services.database.models.org_usage_threshold import (
    OrgUsageThreshold,
    UsageMetric,
    UsagePeriod,
)
from langflow.services.metering.rules import (
    RunSummary,
    eval_consecutive_failures,
    eval_error_rate,
    eval_sla_duration,
)
from langflow.services.metering.thresholds import check_threshold_crossed
from langflow.services.notifier.protocol import UsageAlertEvent

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


async def upsert_org_usage_daily(
    session: "AsyncSession",
    *,
    org_id: UUID,
    day: dt.date,
    runs_delta: int,
    run_seconds_delta: int,
    tokens_delta: int,
    cost_cents_delta: int = 0,
) -> None:
    """Atomic per-(org, date) counter upsert.

    Uses INSERT ... ON CONFLICT DO UPDATE on both Postgres and SQLite so
    two workers completing the same day concurrently never drop a count.
    """
    bind = session.bind
    dialect = bind.dialect.name if bind else "sqlite"
    insert_fn = pg_insert if dialect == "postgresql" else sqlite_insert

    now = datetime.now(timezone.utc)
    stmt = insert_fn(OrgUsageDaily).values(
        org_id=org_id,
        date=day,
        runs=runs_delta,
        run_seconds=run_seconds_delta,
        tokens=tokens_delta,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["org_id", "date"],
        set_={
            "runs": OrgUsageDaily.runs + stmt.excluded.runs,
            "run_seconds": OrgUsageDaily.run_seconds + stmt.excluded.run_seconds,
            "tokens": OrgUsageDaily.tokens + stmt.excluded.tokens,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    await session.exec(stmt)


async def sum_tokens_for_flow_day(
    session: "AsyncSession",
    *,
    flow_id: UUID,
    day: dt.date,
) -> int:
    """Sum total_tokens across traces for a flow on a specific UTC day.

    Attribution window is [start_of_day_utc, end_of_day_utc]; traces with a null
    total_tokens are ignored.
    """
    from langflow.services.database.models.traces.model import TraceTable

    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = datetime.combine(day, time.max, tzinfo=timezone.utc)

    stmt = sm_select(func.coalesce(func.sum(TraceTable.total_tokens), 0)).where(
        TraceTable.flow_id == flow_id,
        TraceTable.start_time >= start,
        TraceTable.start_time <= end,
    )
    result = await session.exec(stmt)
    return int(result.one())


async def upsert_flow_usage_daily(
    session: "AsyncSession",
    *,
    flow_id: UUID,
    org_id: UUID,
    day: dt.date,
    runs_delta: int,
    run_seconds_delta: int,
    tokens_delta: int,
    cost_cents_delta: int,
) -> None:
    """Atomic per-(flow, date) counter upsert for FlowUsageDaily."""
    from langflow.services.database.models.flow_usage_daily import FlowUsageDaily

    bind = session.bind
    dialect = bind.dialect.name if bind else "sqlite"
    insert_fn = pg_insert if dialect == "postgresql" else sqlite_insert

    now = datetime.now(timezone.utc)
    stmt = insert_fn(FlowUsageDaily).values(
        flow_id=flow_id,
        date=day,
        org_id=org_id,
        runs=runs_delta,
        run_seconds=run_seconds_delta,
        tokens=tokens_delta,
        cost_cents=cost_cents_delta,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["flow_id", "date"],
        set_={
            "runs": FlowUsageDaily.runs + stmt.excluded.runs,
            "run_seconds": FlowUsageDaily.run_seconds + stmt.excluded.run_seconds,
            "tokens": FlowUsageDaily.tokens + stmt.excluded.tokens,
            "cost_cents": FlowUsageDaily.cost_cents + stmt.excluded.cost_cents,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    await session.exec(stmt)


@dataclass(frozen=True)
class _DailyCounters:
    runs: int
    run_seconds: int
    tokens: int

    def value_for(self, metric: UsageMetric) -> int:
        if metric is UsageMetric.RUNS:
            return self.runs
        if metric is UsageMetric.RUN_SECONDS:
            return self.run_seconds
        return self.tokens


async def record_run_completion_and_eval(
    session: "AsyncSession",
    *,
    run: FlowRun,
    dispatcher,
) -> None:
    """Single entry point called from the worker post-commit hook.

    Upserts org_usage_daily, sums tokens for the run's day, evaluates
    thresholds + alert rules with row-level locks + cooldowns, and fires
    events through the UsageAlertDispatcher.
    """
    if run.organization_id is None or run.finished_at is None:
        return

    day = run.finished_at.astimezone(timezone.utc).date()
    duration_s = 0
    if run.started_at is not None:
        started = run.started_at
        finished = run.finished_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if finished.tzinfo is None:
            finished = finished.replace(tzinfo=timezone.utc)
        duration_s = int(max(0, (finished - started).total_seconds()))

    tokens = 0
    if run.flow_id is not None:
        tokens = await sum_tokens_for_flow_day(session, flow_id=run.flow_id, day=day)

    # Cost computation (gated by settings.cost_tracking_enabled).
    cost_cents = 0
    model_usage: dict[str, Any] = {}
    try:
        from langflow.services.deps import get_pricing_service, get_settings_service
        if get_settings_service().settings.cost_tracking_enabled and run.flow_id is not None:
            from langflow.services.cost.compute import compute_cost_for_run
            pricing = get_pricing_service()
            cost_cents, model_usage = await compute_cost_for_run(
                session, flow_run_id=run.id, pricing=pricing
            )
            run.cost_cents = cost_cents
            run.model_usage = model_usage or None
            session.add(run)
    except Exception:  # noqa: BLE001
        logger.exception("cost computation failed for run %s", run.id)
        cost_cents = 0
        model_usage = {}

    # Re-read pre-increment counters so threshold eval sees the crossing delta.
    existing = (
        await session.exec(
            sm_select(OrgUsageDaily).where(
                OrgUsageDaily.org_id == run.organization_id,
                OrgUsageDaily.date == day,
            )
        )
    ).first()
    previous = _DailyCounters(
        runs=existing.runs if existing else 0,
        run_seconds=existing.run_seconds if existing else 0,
        tokens=existing.tokens if existing else 0,
    )

    await upsert_org_usage_daily(
        session,
        org_id=run.organization_id,
        day=day,
        runs_delta=1,
        run_seconds_delta=duration_s,
        tokens_delta=tokens,
        cost_cents_delta=cost_cents,
    )
    if run.flow_id is not None:
        await upsert_flow_usage_daily(
            session,
            flow_id=run.flow_id,
            org_id=run.organization_id,
            day=day,
            runs_delta=1,
            run_seconds_delta=duration_s,
            tokens_delta=tokens,
            cost_cents_delta=cost_cents,
        )
    current = _DailyCounters(
        runs=previous.runs + 1,
        run_seconds=previous.run_seconds + duration_s,
        tokens=previous.tokens + tokens,
    )

    events: list[UsageAlertEvent] = []
    events.extend(
        await _eval_thresholds(session, run.organization_id, previous, current, day)
    )
    events.extend(await _eval_alert_rules(session, run, duration_s))

    await session.flush()  # stamp last_fired_at updates before dispatch

    for event in events:
        await dispatcher.dispatch(event)


async def _eval_thresholds(
    session: "AsyncSession",
    org_id: UUID,
    previous: _DailyCounters,
    current: _DailyCounters,
    day: dt.date,
) -> list[UsageAlertEvent]:
    # Row-lock active thresholds for this org to serialize concurrent workers.
    thresholds = (
        await session.exec(
            sm_select(OrgUsageThreshold)
            .where(
                OrgUsageThreshold.org_id == org_id,
                OrgUsageThreshold.is_active.is_(True),
            )
            .with_for_update(skip_locked=True)
        )
    ).all()

    now = datetime.now(timezone.utc)
    events: list[UsageAlertEvent] = []

    for t in thresholds:
        # v1 supports daily period only; monthly is a P1 extension. Skip non-daily.
        if t.period is not UsagePeriod.DAILY:
            continue
        prev_v = previous.value_for(t.metric)
        cur_v = current.value_for(t.metric)
        if not check_threshold_crossed(t, previous=prev_v, current=cur_v, now=now):
            continue

        t.last_fired_at = now
        session.add(t)
        events.append(
            UsageAlertEvent(
                category="usage_threshold",
                severity="warning",
                org_id=org_id,
                title=f"{t.metric.value} threshold crossed ({t.threshold_value}) for {day.isoformat()}",
                body_md=(
                    f"Org `{org_id}` crossed the {t.period.value} {t.metric.value} "
                    f"threshold of **{t.threshold_value}** (observed: {cur_v})."
                ),
                metadata={
                    "threshold_id": str(t.id),
                    "metric": t.metric.value,
                    "period": t.period.value,
                    "threshold_value": t.threshold_value,
                    "observed_value": cur_v,
                    "day": day.isoformat(),
                },
            )
        )
    return events


async def _eval_alert_rules(
    session: "AsyncSession",
    run: FlowRun,
    duration_s: int,
) -> list[UsageAlertEvent]:
    rules = (
        await session.exec(
            sm_select(AlertRule)
            .where(
                AlertRule.org_id == run.organization_id,
                AlertRule.is_active.is_(True),
                or_(AlertRule.flow_id.is_(None), AlertRule.flow_id == run.flow_id),
            )
            .with_for_update(skip_locked=True)
        )
    ).all()

    if not rules:
        return []

    now = datetime.now(timezone.utc)
    largest_window = max(
        int(r.config.get("window_minutes", 60)) for r in rules if r.rule_type is AlertRuleType.ERROR_RATE
    ) if any(r.rule_type is AlertRuleType.ERROR_RATE for r in rules) else 0
    max_n = max(
        int(r.config.get("n", 1)) for r in rules if r.rule_type is AlertRuleType.CONSECUTIVE_FAILURES
    ) if any(r.rule_type is AlertRuleType.CONSECUTIVE_FAILURES for r in rules) else 0

    recent_runs: list[RunSummary] = []
    if max_n > 0 or largest_window > 0:
        window_start = now - timedelta(minutes=max(largest_window, 60))
        records = (
            await session.exec(
                sm_select(FlowRun.status, FlowRun.finished_at, FlowRun.started_at)
                .where(
                    FlowRun.flow_id == run.flow_id,
                    FlowRun.finished_at.is_not(None),
                    FlowRun.finished_at >= window_start,
                )
                .order_by(FlowRun.finished_at.desc())
                .limit(max(max_n, 500))
            )
        ).all()
        for status, finished_at, started_at in records:
            dur = 0.0
            if started_at and finished_at:
                s = started_at if started_at.tzinfo else started_at.replace(tzinfo=timezone.utc)
                f = finished_at if finished_at.tzinfo else finished_at.replace(tzinfo=timezone.utc)
                dur = max(0.0, (f - s).total_seconds())
            recent_runs.append(RunSummary(status=status, finished_at=finished_at, duration_seconds=dur))

    current_summary = RunSummary(
        status=run.status, finished_at=run.finished_at, duration_seconds=float(duration_s)
    )

    events: list[UsageAlertEvent] = []
    for rule in rules:
        fired = False
        if rule.rule_type is AlertRuleType.CONSECUTIVE_FAILURES:
            fired = eval_consecutive_failures(rule, recent_runs=recent_runs, now=now)
        elif rule.rule_type is AlertRuleType.ERROR_RATE:
            window = int(rule.config.get("window_minutes", 60))
            windowed = [r for r in recent_runs if r.finished_at >= now - timedelta(minutes=window)]
            fired = eval_error_rate(rule, recent_runs=windowed, now=now)
        elif rule.rule_type is AlertRuleType.SLA_DURATION:
            fired = eval_sla_duration(rule, current_run=current_summary)

        if not fired:
            continue

        rule.last_fired_at = now
        session.add(rule)
        events.append(
            UsageAlertEvent(
                category="alert_rule",
                severity="warning",
                org_id=run.organization_id,
                title=f"Alert rule fired: {rule.rule_type.value}",
                body_md=(
                    f"Rule `{rule.id}` ({rule.rule_type.value}) fired on flow "
                    f"`{run.flow_id}` after run `{run.id}`."
                ),
                metadata={
                    "rule_id": str(rule.id),
                    "rule_type": rule.rule_type.value,
                    "flow_id": str(run.flow_id) if run.flow_id else None,
                    "run_id": str(run.id),
                    "config": dict(rule.config),
                },
            )
        )
    return events

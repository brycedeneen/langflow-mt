from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from langflow.services.database.models.alert_rule import AlertRule, AlertRuleType
from langflow.services.database.models.flow_run.model import RunStatus
from langflow.services.metering.rules import (
    RunSummary,
    eval_consecutive_failures,
    eval_error_rate,
    eval_sla_duration,
    is_failure,
)


def _rule(rule_type: AlertRuleType, config: dict) -> AlertRule:
    return AlertRule(
        id=uuid4(),
        org_id=uuid4(),
        flow_id=None,
        rule_type=rule_type,
        config=config,
        is_active=True,
        last_fired_at=None,
        cooldown_seconds=0,
        created_by_user_id=uuid4(),
    )


def _summary(status: RunStatus, finished: datetime, duration_s: float = 5.0) -> RunSummary:
    return RunSummary(
        status=status,
        finished_at=finished,
        duration_seconds=duration_s,
    )


def test_is_failure_classifies_terminal_states():
    assert is_failure(RunStatus.FAILED)
    assert is_failure(RunStatus.TIMED_OUT)
    assert not is_failure(RunStatus.SUCCEEDED)
    assert not is_failure(RunStatus.CANCELLED)


def test_consecutive_failures_fires_at_threshold():
    rule = _rule(AlertRuleType.CONSECUTIVE_FAILURES, {"n": 3})
    now = datetime.now(timezone.utc)
    recent = [
        _summary(RunStatus.FAILED, now - timedelta(minutes=i)) for i in range(3)
    ]
    assert eval_consecutive_failures(rule, recent_runs=recent, now=now) is True


def test_consecutive_failures_breaks_on_success():
    rule = _rule(AlertRuleType.CONSECUTIVE_FAILURES, {"n": 3})
    now = datetime.now(timezone.utc)
    recent = [
        _summary(RunStatus.FAILED, now - timedelta(minutes=1)),
        _summary(RunStatus.SUCCEEDED, now - timedelta(minutes=2)),
        _summary(RunStatus.FAILED, now - timedelta(minutes=3)),
    ]
    assert eval_consecutive_failures(rule, recent_runs=recent, now=now) is False


def test_error_rate_needs_min_samples():
    rule = _rule(AlertRuleType.ERROR_RATE, {"window_minutes": 60, "min_samples": 10, "rate_pct": 50})
    now = datetime.now(timezone.utc)
    small_sample = [_summary(RunStatus.FAILED, now) for _ in range(5)]
    assert eval_error_rate(rule, recent_runs=small_sample, now=now) is False


def test_error_rate_fires_on_crossing():
    rule = _rule(AlertRuleType.ERROR_RATE, {"window_minutes": 60, "min_samples": 10, "rate_pct": 20})
    now = datetime.now(timezone.utc)
    runs = (
        [_summary(RunStatus.FAILED, now) for _ in range(3)]
        + [_summary(RunStatus.SUCCEEDED, now) for _ in range(7)]
    )
    # 3/10 = 30% >= 20% → fire
    assert eval_error_rate(rule, recent_runs=runs, now=now) is True


def test_sla_duration_fires_when_exceeded():
    rule = _rule(AlertRuleType.SLA_DURATION, {"max_seconds": 120})
    current = _summary(RunStatus.SUCCEEDED, datetime.now(timezone.utc), duration_s=200)
    assert eval_sla_duration(rule, current_run=current) is True


def test_sla_duration_does_not_fire_under_budget():
    rule = _rule(AlertRuleType.SLA_DURATION, {"max_seconds": 120})
    current = _summary(RunStatus.SUCCEEDED, datetime.now(timezone.utc), duration_s=60)
    assert eval_sla_duration(rule, current_run=current) is False


def test_cooldown_gates_all_rule_types():
    now = datetime.now(timezone.utc)
    for rt, cfg, runs, current in [
        (AlertRuleType.CONSECUTIVE_FAILURES, {"n": 1}, [_summary(RunStatus.FAILED, now)], None),
        (AlertRuleType.ERROR_RATE, {"window_minutes": 60, "min_samples": 1, "rate_pct": 1},
         [_summary(RunStatus.FAILED, now)], None),
        (AlertRuleType.SLA_DURATION, {"max_seconds": 1}, [], _summary(RunStatus.SUCCEEDED, now, duration_s=999)),
    ]:
        rule = _rule(rt, cfg)
        rule.last_fired_at = now - timedelta(seconds=1)
        rule.cooldown_seconds = 600  # 10 min

        if rt is AlertRuleType.CONSECUTIVE_FAILURES:
            fired = eval_consecutive_failures(rule, recent_runs=runs, now=now)
        elif rt is AlertRuleType.ERROR_RATE:
            fired = eval_error_rate(rule, recent_runs=runs, now=now)
        else:
            fired = eval_sla_duration(rule, current_run=current)

        assert fired is False

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

from langflow.services.database.models.alert_rule import AlertRule, AlertRuleType
from langflow.services.database.models.flow_run.model import RunStatus


_FAILURE_STATES: frozenset[RunStatus] = frozenset({RunStatus.FAILED, RunStatus.TIMED_OUT})


def is_failure(status: RunStatus) -> bool:
    return status in _FAILURE_STATES


@dataclass(frozen=True)
class RunSummary:
    status: RunStatus
    finished_at: datetime
    duration_seconds: float


def _cooldown_elapsed(rule: AlertRule, now: datetime) -> bool:
    if rule.last_fired_at is None:
        return True
    return (now - rule.last_fired_at) >= timedelta(seconds=rule.cooldown_seconds)


def eval_consecutive_failures(
    rule: AlertRule,
    *,
    recent_runs: Sequence[RunSummary],  # ordered most-recent-first
    now: datetime,
) -> bool:
    if not rule.is_active or not _cooldown_elapsed(rule, now):
        return False
    n = int(rule.config.get("n", 0))
    if n <= 0 or len(recent_runs) < n:
        return False
    return all(is_failure(r.status) for r in recent_runs[:n])


def eval_error_rate(
    rule: AlertRule,
    *,
    recent_runs: Sequence[RunSummary],  # already filtered to window
    now: datetime,
) -> bool:
    if not rule.is_active or not _cooldown_elapsed(rule, now):
        return False
    min_samples = int(rule.config.get("min_samples", 1))
    rate_pct = float(rule.config.get("rate_pct", 100))
    if len(recent_runs) < min_samples:
        return False
    failures = sum(1 for r in recent_runs if is_failure(r.status))
    observed_pct = (failures * 100.0) / len(recent_runs)
    return observed_pct >= rate_pct


def eval_sla_duration(
    rule: AlertRule,
    *,
    current_run: RunSummary,
) -> bool:
    if not rule.is_active:
        return False
    if not _cooldown_elapsed(rule, current_run.finished_at):
        return False
    max_seconds = float(rule.config.get("max_seconds", float("inf")))
    return current_run.duration_seconds > max_seconds

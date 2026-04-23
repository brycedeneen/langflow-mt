from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from langflow.services.database.models.org_usage_threshold import (
    OrgUsageThreshold,
    UsageMetric,
    UsagePeriod,
)
from langflow.services.metering.thresholds import check_threshold_crossed


def _threshold(**over) -> OrgUsageThreshold:
    defaults = dict(
        id=uuid4(),
        org_id=uuid4(),
        metric=UsageMetric.RUNS,
        period=UsagePeriod.DAILY,
        threshold_value=100,
        is_active=True,
        last_fired_at=None,
        cooldown_seconds=3600,
        created_by_user_id=uuid4(),
    )
    defaults.update(over)
    return OrgUsageThreshold(**defaults)


def test_crossing_upward_fires():
    t = _threshold(threshold_value=100)
    assert check_threshold_crossed(t, previous=99, current=101, now=datetime.now(timezone.utc)) is True


def test_exactly_hitting_the_threshold_fires():
    t = _threshold(threshold_value=100)
    assert check_threshold_crossed(t, previous=99, current=100, now=datetime.now(timezone.utc)) is True


def test_already_above_does_not_re_fire():
    t = _threshold(threshold_value=100)
    assert check_threshold_crossed(t, previous=120, current=150, now=datetime.now(timezone.utc)) is False


def test_below_threshold_does_not_fire():
    t = _threshold(threshold_value=100)
    assert check_threshold_crossed(t, previous=50, current=75, now=datetime.now(timezone.utc)) is False


def test_inactive_threshold_does_not_fire():
    t = _threshold(threshold_value=100, is_active=False)
    assert check_threshold_crossed(t, previous=99, current=101, now=datetime.now(timezone.utc)) is False


def test_cooldown_suppresses_re_fire():
    now = datetime.now(timezone.utc)
    t = _threshold(
        threshold_value=100,
        last_fired_at=now - timedelta(minutes=30),
        cooldown_seconds=3600,  # 1 hr
    )
    assert check_threshold_crossed(t, previous=150, current=200, now=now) is False


def test_cooldown_elapsed_allows_re_fire_on_new_crossing():
    now = datetime.now(timezone.utc)
    t = _threshold(
        threshold_value=100,
        last_fired_at=now - timedelta(hours=2),
        cooldown_seconds=3600,
    )
    # The counters reset at period boundary, so a new crossing looks like 80 -> 120.
    assert check_threshold_crossed(t, previous=80, current=120, now=now) is True

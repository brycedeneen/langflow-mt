from __future__ import annotations

from datetime import datetime, timedelta

from langflow.services.database.models.org_usage_threshold import OrgUsageThreshold


def check_threshold_crossed(
    threshold: OrgUsageThreshold,
    *,
    previous: int,
    current: int,
    now: datetime,
) -> bool:
    """Return True iff this is a fresh upward crossing that clears cooldown."""
    if not threshold.is_active:
        return False
    if current < threshold.threshold_value:
        return False
    if previous >= threshold.threshold_value:
        # Already above — only re-fire on a fresh crossing (handled by period reset).
        return False
    if threshold.last_fired_at is not None:
        elapsed = now - threshold.last_fired_at
        if elapsed < timedelta(seconds=threshold.cooldown_seconds):
            return False
    return True

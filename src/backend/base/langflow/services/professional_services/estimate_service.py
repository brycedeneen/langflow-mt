from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

DEFAULT_MINUTES_LOW = 15
DEFAULT_MINUTES_HIGH = 60


@dataclass(frozen=True)
class MinutesEstimate:
    low: int
    high: int
    breakdown: list[dict[str, Any]]


def sum_component_minutes(
    nodes: list[dict[str, Any]],
    metadata_by_type: dict[str, tuple[int | None, int | None]],
) -> MinutesEstimate:
    """Sum integration_minutes_low/high across all flow nodes.

    `metadata_by_type` maps component_name -> (low, high). Missing types or
    NULL columns fall back to DEFAULT_MINUTES_LOW / DEFAULT_MINUTES_HIGH.
    """
    breakdown: list[dict[str, Any]] = []
    total_low = 0
    total_high = 0
    for node in nodes:
        component_type = node.get("data", {}).get("type", "Unknown")
        meta_low, meta_high = metadata_by_type.get(component_type, (None, None))
        low = meta_low if meta_low is not None else DEFAULT_MINUTES_LOW
        high = meta_high if meta_high is not None else DEFAULT_MINUTES_HIGH
        breakdown.append(
            {"type": component_type, "minutes_low": low, "minutes_high": high}
        )
        total_low += low
        total_high += high
    return MinutesEstimate(low=total_low, high=total_high, breakdown=breakdown)


def compute_cost_range(
    minutes_low: int,
    minutes_high: int,
    rate_low_per_hour: Decimal | None,
    rate_high_per_hour: Decimal | None,
) -> tuple[Decimal | None, Decimal | None]:
    """Compute dollar cost range from minutes × rate. Returns (None, None) if
    either rate is unset (graceful degradation)."""
    if rate_low_per_hour is None or rate_high_per_hour is None:
        return (None, None)
    sixty = Decimal("60")
    cost_low = (Decimal(minutes_low) * rate_low_per_hour / sixty).quantize(Decimal("0.01"))
    cost_high = (Decimal(minutes_high) * rate_high_per_hour / sixty).quantize(Decimal("0.01"))
    return (cost_low, cost_high)

from decimal import Decimal

from langflow.services.professional_services.estimate_service import (
    MinutesEstimate,
    compute_cost_range,
    sum_component_minutes,
)


def test_sum_component_minutes_uses_metadata_when_available():
    nodes = [
        {"data": {"type": "OpenAIModel"}},
        {"data": {"type": "Webhook"}},
    ]
    metadata_by_type = {
        "OpenAIModel": (30, 90),
        "Webhook": (10, 45),
    }
    estimate = sum_component_minutes(nodes, metadata_by_type)
    assert estimate == MinutesEstimate(low=40, high=135, breakdown=[
        {"type": "OpenAIModel", "minutes_low": 30, "minutes_high": 90},
        {"type": "Webhook", "minutes_low": 10, "minutes_high": 45},
    ])


def test_sum_component_minutes_falls_back_to_defaults():
    nodes = [{"data": {"type": "UnknownComponent"}}]
    estimate = sum_component_minutes(nodes, metadata_by_type={})
    assert estimate.low == 15
    assert estimate.high == 60


def test_compute_cost_range_basic():
    cost_low, cost_high = compute_cost_range(
        minutes_low=180, minutes_high=720,
        rate_low_per_hour=Decimal("200.00"), rate_high_per_hour=Decimal("200.00"),
    )
    assert cost_low == Decimal("600.00")
    assert cost_high == Decimal("2400.00")


def test_compute_cost_range_returns_none_when_rate_unset():
    cost_low, cost_high = compute_cost_range(
        minutes_low=60, minutes_high=120,
        rate_low_per_hour=None, rate_high_per_hour=None,
    )
    assert cost_low is None
    assert cost_high is None

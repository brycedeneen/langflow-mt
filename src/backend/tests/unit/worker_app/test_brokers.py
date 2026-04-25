from __future__ import annotations

import pytest


def test_registry_exposes_four_brokers():
    from langflow.worker_app import brokers

    assert brokers.broker_high.queue_name == "runs:high"
    assert brokers.broker_default.queue_name == "runs:default"
    assert brokers.broker_low.queue_name == "runs:low"
    assert brokers.broker_webhooks.queue_name == "webhooks"


def test_tier_to_broker_map():
    from langflow.worker_app import brokers

    assert brokers.TIER_TO_BROKER["high"] is brokers.broker_high
    assert brokers.TIER_TO_BROKER["default"] is brokers.broker_default
    assert brokers.TIER_TO_BROKER["low"] is brokers.broker_low


def test_all_brokers_includes_webhooks():
    from langflow.worker_app import brokers

    assert brokers.broker_webhooks in brokers.ALL_BROKERS
    assert len(brokers.ALL_BROKERS) == 4

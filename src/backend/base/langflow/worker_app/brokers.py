"""Central registry of Taskiq brokers for distributed flow execution.

One ListQueueBroker per priority tier — explicit and type-safe vs arq's
string-based `_queue_name`. The enqueuer picks a broker via `TIER_TO_BROKER`;
workers mount one or more brokers at startup.

A single shared RedisAsyncResultBackend is attached to every broker. Results
are not currently consumed (DB row is the source of truth) but having the
backend in place makes the deferred follow-up (broker-side job-status
polling) a config flip.
"""
from __future__ import annotations

from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from lfx.services.settings.base import Settings


_settings = Settings(_env_file=None)
_redis_url = _settings.redis_url

result_backend = RedisAsyncResultBackend(redis_url=_redis_url)

broker_high = ListQueueBroker(
    url=_redis_url, queue_name="runs:high"
).with_result_backend(result_backend)

broker_default = ListQueueBroker(
    url=_redis_url, queue_name="runs:default"
).with_result_backend(result_backend)

broker_low = ListQueueBroker(
    url=_redis_url, queue_name="runs:low"
).with_result_backend(result_backend)

broker_webhooks = ListQueueBroker(
    url=_redis_url, queue_name="webhooks"
).with_result_backend(result_backend)


TIER_TO_BROKER = {
    "high": broker_high,
    "default": broker_default,
    "low": broker_low,
}

ALL_BROKERS = [broker_high, broker_default, broker_low, broker_webhooks]

"""Broker lifespan helpers for the FastAPI app.

Taskiq brokers self-manage their underlying Redis connections; the API
process only needs to call startup/shutdown to enable enqueueing.
"""
from __future__ import annotations

from langflow.worker_app.brokers import ALL_BROKERS


async def startup_brokers() -> None:
    for broker in ALL_BROKERS:
        await broker.startup()


async def shutdown_brokers() -> None:
    for broker in ALL_BROKERS:
        await broker.shutdown()

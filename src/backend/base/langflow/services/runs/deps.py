"""Broker lifespan helpers for the FastAPI app.

Taskiq brokers self-manage their underlying Redis connections; the API
process only needs to call startup/shutdown to enable enqueueing.
"""
from __future__ import annotations

import asyncio

from lfx.log.logger import logger

from langflow.worker_app.brokers import ALL_BROKERS


async def startup_brokers() -> None:
    """Start every Taskiq broker in ALL_BROKERS.

    Fail-fast: if any broker.startup() raises, the app fails to start. We do
    not catch — without a working broker, enqueueing would silently no-op.
    """
    for broker in ALL_BROKERS:
        await broker.startup()


async def shutdown_brokers() -> None:
    """Shut down every Taskiq broker in ALL_BROKERS.

    Exception-safe: a failure shutting down one broker does not block the
    others. Errors are logged but not raised, since shutdown is best-effort.
    """
    results = await asyncio.gather(
        *(broker.shutdown() for broker in ALL_BROKERS),
        return_exceptions=True,
    )
    for broker, result in zip(ALL_BROKERS, results, strict=False):
        if isinstance(result, BaseException):
            logger.warning(f"broker shutdown failed: {broker} → {result!r}")

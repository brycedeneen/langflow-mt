"""In-flight execute_run tracking + graceful drain helper.

`register(task)` and `unregister(task)` are called by execute_run wrappers.
`drain(timeout)` is invoked from the WORKER_SHUTDOWN lifecycle hook to
wait for in-flight tasks to terminate naturally (so they release their
org-concurrency slots and write terminal state to FlowRun).
"""
from __future__ import annotations

import asyncio
import time
from typing import Set

from lfx.log.logger import logger

_registry: Set[asyncio.Task] = set()


def register(task: asyncio.Task) -> None:
    _registry.add(task)


def unregister(task: asyncio.Task) -> None:
    _registry.discard(task)


async def drain(timeout: float) -> float:
    """Wait up to `timeout` seconds for tracked tasks to complete.

    Returns the elapsed wall time (seconds). Tasks still running after the
    timeout are left untouched — Taskiq is about to terminate the process.
    """
    if not _registry:
        return 0.0
    start = time.monotonic()
    pending = list(_registry)
    logger.info(f"[shutdown] draining {len(pending)} in-flight execute_run task(s) (timeout={timeout}s)")
    done, still_pending = await asyncio.wait(pending, timeout=timeout)
    elapsed = time.monotonic() - start
    if still_pending:
        logger.warning(
            f"[shutdown] drain timed out after {elapsed:.2f}s with "
            f"{len(still_pending)} task(s) still running"
        )
    else:
        logger.info(f"[shutdown] drain complete in {elapsed:.2f}s ({len(done)} task(s))")
    return elapsed

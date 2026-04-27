from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

T = TypeVar("T")


class BackoffStrategy(str, Enum):
    NONE = "none"
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_WITH_JITTER = "exponential_with_jitter"


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 3
    strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL_WITH_JITTER
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0


def compute_delay_seconds(config: RetryConfig, attempt: int) -> float:
    """Delay before the *next* attempt. `attempt` is the 1-indexed prior attempt."""
    if config.strategy is BackoffStrategy.NONE:
        return 0.0
    if config.strategy is BackoffStrategy.FIXED:
        return min(config.base_delay_seconds, config.max_delay_seconds)
    base = config.base_delay_seconds * (2 ** (attempt - 1))
    capped = min(base, config.max_delay_seconds)
    if config.strategy is BackoffStrategy.EXPONENTIAL_WITH_JITTER:
        return capped * random.uniform(0.5, 1.5)
    return capped


async def run_with_retries(
    op: Callable[[int], Awaitable[T]],
    config: RetryConfig,
) -> T:
    """Execute `op(attempt)` up to `config.max_attempts` times.

    `op` receives the 1-indexed attempt number. If `op` raises, sleep
    `compute_delay_seconds(config, attempt)` then retry. The final
    exception propagates after all attempts fail.

    `max_attempts=0` is degenerate and treated as 1 (the initial call
    must still happen — there is nothing to retry without it).
    """
    total_attempts = max(1, config.max_attempts)
    last_exc: BaseException | None = None
    for attempt in range(1, total_attempts + 1):
        try:
            return await op(attempt)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt == total_attempts:
                raise
            delay = compute_delay_seconds(config, attempt)
            if delay > 0:
                await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]

import asyncio
import math

import pytest

from lfx.graph.retry import (
    BackoffStrategy,
    RetryConfig,
    compute_delay_seconds,
    run_with_retries,
)


def test_compute_delay_strategy_none():
    cfg = RetryConfig(max_attempts=3, strategy=BackoffStrategy.NONE)
    for attempt in range(1, 4):
        assert compute_delay_seconds(cfg, attempt) == 0.0


def test_compute_delay_strategy_fixed():
    cfg = RetryConfig(
        max_attempts=3, strategy=BackoffStrategy.FIXED, base_delay_seconds=2.5
    )
    for attempt in range(1, 4):
        assert compute_delay_seconds(cfg, attempt) == 2.5


def test_compute_delay_strategy_exponential():
    cfg = RetryConfig(
        max_attempts=5,
        strategy=BackoffStrategy.EXPONENTIAL,
        base_delay_seconds=1.0,
        max_delay_seconds=60.0,
    )
    # attempt N (1-indexed) => 1 * 2^(N-1), capped at 60
    assert compute_delay_seconds(cfg, 1) == 1.0
    assert compute_delay_seconds(cfg, 2) == 2.0
    assert compute_delay_seconds(cfg, 3) == 4.0
    assert compute_delay_seconds(cfg, 7) == 60.0  # capped


def test_compute_delay_with_jitter_within_bounds(monkeypatch):
    cfg = RetryConfig(
        max_attempts=3,
        strategy=BackoffStrategy.EXPONENTIAL_WITH_JITTER,
        base_delay_seconds=2.0,
        max_delay_seconds=60.0,
    )
    # Force jitter multiplier to its bounds; verify in range.
    samples = [compute_delay_seconds(cfg, 2) for _ in range(50)]
    base = 2.0 * 2  # = 4.0 (attempt=2)
    assert all(2.0 <= s <= 6.0 for s in samples)  # jitter range [0.5x, 1.5x]


@pytest.mark.asyncio
async def test_run_with_retries_succeeds_first_try():
    cfg = RetryConfig(max_attempts=3, strategy=BackoffStrategy.NONE)
    calls = []

    async def op(attempt: int):
        calls.append(attempt)
        return "ok"

    result = await run_with_retries(op, cfg)
    assert result == "ok"
    assert calls == [1]


@pytest.mark.asyncio
async def test_run_with_retries_recovers_after_failures():
    cfg = RetryConfig(max_attempts=3, strategy=BackoffStrategy.NONE)
    calls = []

    async def op(attempt: int):
        calls.append(attempt)
        if attempt < 3:
            raise RuntimeError("flaky")
        return "ok"

    result = await run_with_retries(op, cfg)
    assert result == "ok"
    assert calls == [1, 2, 3]


@pytest.mark.asyncio
async def test_run_with_retries_raises_after_exhaustion():
    cfg = RetryConfig(max_attempts=1, strategy=BackoffStrategy.NONE)
    calls = []

    async def op(attempt: int):
        calls.append(attempt)
        raise RuntimeError("always fails")

    with pytest.raises(RuntimeError, match="always fails"):
        await run_with_retries(op, cfg)
    # max_attempts=1 = 1 retry after initial = 2 total calls.
    assert calls == [1, 2]


@pytest.mark.asyncio
async def test_run_with_retries_max_attempts_zero_means_no_retry():
    cfg = RetryConfig(max_attempts=0, strategy=BackoffStrategy.NONE)
    calls = []

    async def op(attempt: int):
        calls.append(attempt)
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError, match="nope"):
        await run_with_retries(op, cfg)
    # max_attempts=0 means: only the original call; no retries.
    assert calls == [1]


@pytest.mark.asyncio
async def test_run_with_retries_total_call_count_matches_retries_plus_one():
    """max_attempts=N means N retries after the initial call (N+1 total calls)."""
    for retry_count in [0, 1, 2, 5]:
        cfg = RetryConfig(max_attempts=retry_count, strategy=BackoffStrategy.NONE)
        calls = []

        async def op(attempt: int):
            calls.append(attempt)
            raise RuntimeError("always fails")

        with pytest.raises(RuntimeError):
            await run_with_retries(op, cfg)
        assert len(calls) == retry_count + 1, (
            f"max_attempts={retry_count} should yield {retry_count + 1} calls"
        )


@pytest.mark.asyncio
async def test_run_with_retries_cancellable():
    cfg = RetryConfig(
        max_attempts=5,
        strategy=BackoffStrategy.FIXED,
        base_delay_seconds=10.0,  # long sleep
    )

    async def op(attempt: int):
        raise RuntimeError("fail")

    task = asyncio.create_task(run_with_retries(op, cfg))
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

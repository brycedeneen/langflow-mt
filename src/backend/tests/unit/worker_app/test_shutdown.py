from __future__ import annotations
import asyncio
import pytest

pytestmark = pytest.mark.asyncio


async def test_register_unregister_tracks_tasks():
    from langflow.worker_app.shutdown import _registry, register, unregister

    _registry.clear()

    async def work():
        await asyncio.sleep(0.01)

    t = asyncio.create_task(work())
    register(t)
    assert t in _registry
    await t
    unregister(t)
    assert t not in _registry


async def test_drain_waits_for_inflight():
    from langflow.worker_app.shutdown import _registry, drain, register

    _registry.clear()

    async def slow():
        await asyncio.sleep(0.1)

    t = asyncio.create_task(slow())
    register(t)
    duration = await drain(timeout=5.0)
    assert duration >= 0.1
    assert t.done()


async def test_drain_times_out():
    from langflow.worker_app.shutdown import _registry, drain, register

    _registry.clear()

    async def forever():
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            raise

    t = asyncio.create_task(forever())
    register(t)
    duration = await drain(timeout=0.1)
    assert duration >= 0.1
    t.cancel()
    try:
        await t
    except asyncio.CancelledError:
        pass


async def test_drain_no_tasks_returns_zero():
    from langflow.worker_app.shutdown import _registry, drain

    _registry.clear()
    assert await drain(timeout=5.0) == 0.0

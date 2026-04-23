from __future__ import annotations

from uuid import uuid4

import pytest

from langflow.services.notifier.dispatcher import UsageAlertDispatcher
from langflow.services.notifier.protocol import UsageAlertEvent


def _event() -> UsageAlertEvent:
    return UsageAlertEvent(
        category="usage_threshold",
        severity="warning",
        org_id=uuid4(),
        title="test",
        body_md="x",
        metadata={},
    )


class _Recorder:
    def __init__(self) -> None:
        self.seen: list[UsageAlertEvent] = []

    async def notify(self, event: UsageAlertEvent) -> None:
        self.seen.append(event)


class _Exploder:
    async def notify(self, event: UsageAlertEvent) -> None:
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_dispatcher_fans_out_to_all_notifiers():
    a, b = _Recorder(), _Recorder()
    dispatcher = UsageAlertDispatcher([a, b])
    event = _event()

    await dispatcher.dispatch(event)

    assert a.seen == [event]
    assert b.seen == [event]


@pytest.mark.asyncio
async def test_dispatcher_isolates_notifier_failures():
    good = _Recorder()
    dispatcher = UsageAlertDispatcher([_Exploder(), good])
    event = _event()

    # Must not raise even though one notifier raises.
    await dispatcher.dispatch(event)

    assert good.seen == [event]


@pytest.mark.asyncio
async def test_dispatcher_with_empty_notifier_list_is_noop():
    dispatcher = UsageAlertDispatcher([])
    # Must not raise
    await dispatcher.dispatch(_event())

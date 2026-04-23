from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlmodel import select

from langflow.services.database.models.org_usage_daily import OrgUsageDaily
from langflow.services.metering.service import upsert_org_usage_daily


@pytest.mark.asyncio
async def test_upsert_creates_row_when_absent(session_factory):
    org_id = uuid4()
    day = date(2026, 4, 22)

    async with session_factory() as session:
        await upsert_org_usage_daily(
            session,
            org_id=org_id,
            day=day,
            runs_delta=1,
            run_seconds_delta=30,
            tokens_delta=1250,
        )
        await session.commit()

        row = (
            await session.exec(
                select(OrgUsageDaily).where(OrgUsageDaily.org_id == org_id, OrgUsageDaily.date == day)
            )
        ).one()

    assert row.runs == 1
    assert row.run_seconds == 30
    assert row.tokens == 1250


@pytest.mark.asyncio
async def test_upsert_accumulates_into_existing_row(session_factory):
    org_id = uuid4()
    day = date(2026, 4, 22)

    async with session_factory() as session:
        await upsert_org_usage_daily(session, org_id=org_id, day=day, runs_delta=1, run_seconds_delta=10, tokens_delta=100)
        await upsert_org_usage_daily(session, org_id=org_id, day=day, runs_delta=2, run_seconds_delta=20, tokens_delta=200)
        await session.commit()

        row = (
            await session.exec(
                select(OrgUsageDaily).where(OrgUsageDaily.org_id == org_id, OrgUsageDaily.date == day)
            )
        ).one()

    assert row.runs == 3
    assert row.run_seconds == 30
    assert row.tokens == 300


@pytest.mark.asyncio
async def test_upsert_partitions_by_org_and_date(session_factory):
    org_a, org_b = uuid4(), uuid4()
    d1, d2 = date(2026, 4, 22), date(2026, 4, 23)

    async with session_factory() as session:
        await upsert_org_usage_daily(session, org_id=org_a, day=d1, runs_delta=1, run_seconds_delta=5, tokens_delta=50)
        await upsert_org_usage_daily(session, org_id=org_a, day=d2, runs_delta=1, run_seconds_delta=5, tokens_delta=50)
        await upsert_org_usage_daily(session, org_id=org_b, day=d1, runs_delta=1, run_seconds_delta=5, tokens_delta=50)
        await session.commit()

        all_rows = (await session.exec(select(OrgUsageDaily))).all()

    assert len(all_rows) == 3


@pytest.mark.asyncio
async def test_sum_tokens_for_flow_day(session_factory):
    from langflow.services.database.models.traces.model import TraceTable
    from langflow.services.metering.service import sum_tokens_for_flow_day

    flow_id = uuid4()
    target_day = date(2026, 4, 22)

    async with session_factory() as session:
        # trace on target day, same flow
        trace = TraceTable(
            id=uuid4(),
            name="run",
            flow_id=flow_id,
            total_tokens=500,
            start_time=datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 22, 10, 1, tzinfo=timezone.utc),
        )
        # trace on target day, different flow — must be excluded
        trace_other = TraceTable(
            id=uuid4(),
            name="run",
            flow_id=uuid4(),
            total_tokens=9999,
            start_time=datetime(2026, 4, 22, 11, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 22, 11, 1, tzinfo=timezone.utc),
        )
        # trace on adjacent day — must be excluded
        trace_prev_day = TraceTable(
            id=uuid4(),
            name="run",
            flow_id=flow_id,
            total_tokens=100,
            start_time=datetime(2026, 4, 21, 23, 59, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 21, 23, 59, tzinfo=timezone.utc),
        )
        session.add_all([trace, trace_other, trace_prev_day])
        await session.commit()

        total = await sum_tokens_for_flow_day(session, flow_id=flow_id, day=target_day)

    assert total == 500

from __future__ import annotations

import datetime as dt
from datetime import datetime, time, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import select as sm_select

from langflow.services.database.models.org_usage_daily import OrgUsageDaily

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


async def upsert_org_usage_daily(
    session: "AsyncSession",
    *,
    org_id: UUID,
    day: dt.date,
    runs_delta: int,
    run_seconds_delta: int,
    tokens_delta: int,
    cost_cents_delta: int = 0,
) -> None:
    """Atomic per-(org, date) counter upsert.

    Uses INSERT ... ON CONFLICT DO UPDATE on both Postgres and SQLite so
    two workers completing the same day concurrently never drop a count.
    """
    bind = session.bind
    dialect = bind.dialect.name if bind else "sqlite"
    insert_fn = pg_insert if dialect == "postgresql" else sqlite_insert

    now = datetime.now(timezone.utc)
    stmt = insert_fn(OrgUsageDaily).values(
        org_id=org_id,
        date=day,
        runs=runs_delta,
        run_seconds=run_seconds_delta,
        tokens=tokens_delta,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["org_id", "date"],
        set_={
            "runs": OrgUsageDaily.runs + stmt.excluded.runs,
            "run_seconds": OrgUsageDaily.run_seconds + stmt.excluded.run_seconds,
            "tokens": OrgUsageDaily.tokens + stmt.excluded.tokens,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    await session.exec(stmt)


async def sum_tokens_for_flow_day(
    session: "AsyncSession",
    *,
    flow_id: UUID,
    day: dt.date,
) -> int:
    """Sum total_tokens across traces for a flow on a specific UTC day.

    Attribution window is [start_of_day_utc, end_of_day_utc]; traces with a null
    total_tokens are ignored.
    """
    from langflow.services.database.models.traces.model import TraceTable

    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = datetime.combine(day, time.max, tzinfo=timezone.utc)

    stmt = sm_select(func.coalesce(func.sum(TraceTable.total_tokens), 0)).where(
        TraceTable.flow_id == flow_id,
        TraceTable.start_time >= start,
        TraceTable.start_time <= end,
    )
    result = await session.exec(stmt)
    return int(result.one())

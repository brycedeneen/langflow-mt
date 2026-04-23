from __future__ import annotations

from datetime import date

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.database.models.org_usage_daily import OrgUsageDaily
from langflow.services.deps import session_scope


@pytest.mark.asyncio
async def test_usage_kpi_endpoint_returns_current_period(
    client: AsyncClient,
    logged_in_headers_platform_admin: dict,
    seeded_org,
):
    async with session_scope() as session:
        today = date.today()
        row = OrgUsageDaily(
            org_id=seeded_org.id,
            date=today,
            runs=5,
            run_seconds=300,
            tokens=1500,
            cost_cents=12,
        )
        session.add(row)
        await session.commit()

    resp = await client.get(
        f"api/v1/orgs/{seeded_org.id}/usage?window=7d",
        headers=logged_in_headers_platform_admin,
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["runs"] >= 5
    assert body["run_seconds"] >= 300
    assert body["tokens"] >= 1500
    assert body["cost_cents"] >= 12

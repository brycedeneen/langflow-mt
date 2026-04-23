from __future__ import annotations

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_estimate_cost_endpoint(
    client: AsyncClient,
    logged_in_headers_super_user: dict,
    flow,
):
    resp = await client.post(
        f"api/v1/flows/{flow.id}/estimate-cost",
        headers=logged_in_headers_super_user,
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert "estimate" in body
    assert set(body["estimate"].keys()) >= {
        "expected_cost_cents", "low_cost_cents", "high_cost_cents", "confidence"
    }
    assert "per_component" in body


@pytest.mark.asyncio
async def test_flow_cost_summary_endpoint(
    client: AsyncClient,
    logged_in_headers_super_user: dict,
    flow,
):
    resp = await client.get(
        f"api/v1/flows/{flow.id}/cost-summary",
        headers=logged_in_headers_super_user,
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert "total_cost_cents" in body
    assert "sparkline" in body

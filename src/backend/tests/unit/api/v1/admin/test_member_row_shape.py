"""Tests for the `MemberRow` response shape on admin org endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.usefixtures("client")
async def test_org_detail_members_include_is_active(
    client: AsyncClient, admin_headers, org_with_inactive_member,
):
    r = await client.get(
        f"/api/v1/admin/organizations/{org_with_inactive_member['org_id']}",
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    inactive = next(
        m for m in body["members"]
        if m["user_id"] == str(org_with_inactive_member["inactive_user_id"])
    )
    assert inactive["is_active"] is False

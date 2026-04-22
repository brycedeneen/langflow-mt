"""Tests for the relaxed gates on add/remove member admin endpoints.

Both `POST /api/v1/admin/organizations/{org_id}/members` and
`DELETE /api/v1/admin/organizations/{org_id}/members/{user_id}` were
originally gated by `PlatformAdmin`. They now use `assert_org_role(ADMIN)`
so that org Admin/Owner can also manage members (with escalation guards).
"""
from __future__ import annotations

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.usefixtures("client")
class TestAddMemberGate:
    async def test_org_admin_can_add_member(
        self, client: AsyncClient, org_admin_headers, org_admin_org, another_user
    ):
        """An org Admin may add a Member to the org."""
        org_id = org_admin_org["org_id"]
        resp = await client.post(
            f"api/v1/admin/organizations/{org_id}/members",
            json={"user_id": another_user["id"], "role": "member"},
            headers=org_admin_headers,
        )
        assert resp.status_code == status.HTTP_201_CREATED, resp.text
        data = resp.json()
        assert data["user_id"] == another_user["id"]
        assert data["username"] == another_user["username"]
        assert data["role"] == "member"

    @pytest.mark.parametrize("role", ["admin", "owner"])
    async def test_org_admin_cannot_add_admin_or_owner(
        self,
        client: AsyncClient,
        org_admin_headers,
        org_admin_org,
        another_user,
        role,
    ):
        """An Admin caller may not assign Admin or Owner roles."""
        org_id = org_admin_org["org_id"]
        resp = await client.post(
            f"api/v1/admin/organizations/{org_id}/members",
            json={"user_id": another_user["id"], "role": role},
            headers=org_admin_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN, resp.text

    async def test_member_cannot_add_anyone(
        self, client: AsyncClient, member_headers, org_with_member, another_user
    ):
        """A Member caller is below the Admin minimum → 403."""
        org_id = org_with_member["org_id"]
        resp = await client.post(
            f"api/v1/admin/organizations/{org_id}/members",
            json={"user_id": another_user["id"], "role": "member"},
            headers=member_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN, resp.text


@pytest.mark.usefixtures("client")
class TestRemoveMemberGate:
    async def test_org_admin_can_remove_member(
        self, client: AsyncClient, org_admin_headers, org_admin_org, org_with_member
    ):
        """An org Admin may remove a non-Owner member from the org."""
        org_id = org_admin_org["org_id"]
        # `org_with_member` seeds a Member whose id lives in org_with_member["user_id"].
        target_user_id = org_with_member["user_id"]
        resp = await client.request(
            "DELETE",
            f"api/v1/admin/organizations/{org_id}/members/{target_user_id}",
            headers=org_admin_headers,
        )
        assert resp.status_code == status.HTTP_204_NO_CONTENT, resp.text

    async def test_cannot_remove_last_owner(
        self, client: AsyncClient, admin_headers, sole_owner_org
    ):
        """Platform admin removing the last Owner of a non-personal org → 409."""
        org_id = sole_owner_org["org_id"]
        owner_id = sole_owner_org["owner_id"]
        resp = await client.request(
            "DELETE",
            f"api/v1/admin/organizations/{org_id}/members/{owner_id}",
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_409_CONFLICT, resp.text
        assert "last owner" in resp.json()["detail"].lower()

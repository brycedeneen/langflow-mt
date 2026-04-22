"""Tests for `PATCH /api/v1/admin/organizations/{org_id}/members/{user_id}`."""
from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.deps import session_scope


@pytest.mark.usefixtures("client")
class TestPatchMemberRole:
    async def test_platform_admin_can_promote_to_admin(
        self, client: AsyncClient, admin_headers, org_with_member
    ):
        """Platform admin can promote a Member to Admin."""
        org_id = org_with_member["org_id"]
        user_id = org_with_member["user_id"]
        resp = await client.patch(
            f"api/v1/admin/organizations/{org_id}/members/{user_id}",
            json={"role": "admin"},
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_200_OK, resp.text
        data = resp.json()
        assert data["user_id"] == user_id
        assert data["role"] == "admin"

    async def test_org_admin_cannot_promote_to_admin(
        self, client: AsyncClient, org_admin_headers, org_with_member
    ):
        """An Admin caller may not promote someone *to* Admin."""
        org_id = org_with_member["org_id"]
        user_id = org_with_member["user_id"]
        resp = await client.patch(
            f"api/v1/admin/organizations/{org_id}/members/{user_id}",
            json={"role": "admin"},
            headers=org_admin_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN, resp.text

    async def test_org_admin_can_promote_member_to_operator(
        self, client: AsyncClient, org_admin_headers, org_with_member
    ):
        """Admin can shuffle below-Admin roles."""
        org_id = org_with_member["org_id"]
        user_id = org_with_member["user_id"]
        resp = await client.patch(
            f"api/v1/admin/organizations/{org_id}/members/{user_id}",
            json={"role": "operator"},
            headers=org_admin_headers,
        )
        assert resp.status_code == status.HTTP_200_OK, resp.text
        assert resp.json()["role"] == "operator"

    async def test_cannot_demote_last_owner(
        self, client: AsyncClient, admin_headers, sole_owner_org
    ):
        """Demoting the sole Owner of a non-personal org fails with 409."""
        org_id = sole_owner_org["org_id"]
        owner_id = sole_owner_org["owner_id"]
        resp = await client.patch(
            f"api/v1/admin/organizations/{org_id}/members/{owner_id}",
            json={"role": "member"},
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_409_CONFLICT, resp.text
        assert "last owner" in resp.json()["detail"].lower()

        # Verify no DB change happened.
        async with session_scope() as session:
            m = (
                await session.exec(
                    select(Membership).where(
                        Membership.user_id == UUID(owner_id),
                        Membership.organization_id == UUID(org_id),
                    )
                )
            ).first()
            assert m is not None
            assert m.role == MembershipRole.OWNER

    async def test_personal_org_locked(
        self, client: AsyncClient, admin_headers, personal_org
    ):
        """Role changes on a personal org are rejected with 409."""
        org_id = personal_org["org_id"]
        user_id = personal_org["user_id"]
        resp = await client.patch(
            f"api/v1/admin/organizations/{org_id}/members/{user_id}",
            json={"role": "member"},
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_409_CONFLICT, resp.text

    async def test_viewer_caller_forbidden(
        self, client: AsyncClient, viewer_headers, org_with_member
    ):
        """A Viewer caller is below the Admin minimum → 403."""
        org_id = org_with_member["org_id"]
        user_id = org_with_member["user_id"]
        resp = await client.patch(
            f"api/v1/admin/organizations/{org_id}/members/{user_id}",
            json={"role": "operator"},
            headers=viewer_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN, resp.text

    async def test_invalid_role_rejected(
        self, client: AsyncClient, admin_headers, org_with_member
    ):
        """An unknown role string returns 400."""
        org_id = org_with_member["org_id"]
        user_id = org_with_member["user_id"]
        resp = await client.patch(
            f"api/v1/admin/organizations/{org_id}/members/{user_id}",
            json={"role": "banana"},
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.text

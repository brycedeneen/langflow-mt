from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.database.models.admin_notification import (
    AdminNotification,
    NotificationCategory,
    NotificationSeverity,
)
from langflow.services.deps import session_scope


async def _seed_notification(**over) -> AdminNotification:
    async with session_scope() as session:
        row = AdminNotification(
            org_id=over.get("org_id", uuid4()),
            category=over.get("category", NotificationCategory.USAGE_THRESHOLD),
            severity=over.get("severity", NotificationSeverity.WARNING),
            title=over.get("title", "Test"),
            body_md=over.get("body_md", "body"),
            metadata_json=over.get("metadata_json", {}),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


@pytest.mark.asyncio
async def test_list_notifications_requires_platform_admin(
    client: AsyncClient, logged_in_headers: dict
):
    resp = await client.get("api/v1/admin/notifications", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_list_notifications_returns_unread_by_default(
    client: AsyncClient, logged_in_headers_platform_admin: dict
):
    await _seed_notification(title="A")
    await _seed_notification(title="B")

    resp = await client.get(
        "api/v1/admin/notifications", headers=logged_in_headers_platform_admin
    )
    assert resp.status_code == status.HTTP_200_OK
    items = resp.json()["items"]
    # Items seeded in this test should be included (may include items from other tests)
    titles = {i["title"] for i in items}
    assert "A" in titles
    assert "B" in titles


@pytest.mark.asyncio
async def test_unread_count_endpoint(
    client: AsyncClient, logged_in_headers_platform_admin: dict
):
    resp = await client.get(
        "api/v1/admin/notifications/unread-count",
        headers=logged_in_headers_platform_admin,
    )
    assert resp.status_code == status.HTTP_200_OK
    assert "unread" in resp.json()


@pytest.mark.asyncio
async def test_mark_read(
    client: AsyncClient, logged_in_headers_platform_admin: dict
):
    row = await _seed_notification(title="mark-me-read")

    resp = await client.post(
        f"api/v1/admin/notifications/{row.id}/read",
        headers=logged_in_headers_platform_admin,
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT

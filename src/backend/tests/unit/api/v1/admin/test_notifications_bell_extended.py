"""Phase G regression tests for the audience-aware notification bell endpoints.

These tests assert the visibility semantics introduced when the ``/api/v1/admin/
notifications`` family was opened up to all authenticated users with a SQL
visibility clause replacing the blanket ``PlatformAdmin`` gate. Visibility:

* Rows targeted at the caller (``audience_user_id == caller.id``) are always
  visible.
* Broadcast rows (``audience_user_id IS NULL``) are visible only when the
  caller's role matches: ``is_superuser`` for ``SUPER_ADMIN`` audience,
  ``is_platform_admin`` for ``PLATFORM_ADMIN`` audience.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.admin_notification import (
    AdminNotification,
    NotificationAudience,
    NotificationCategory,
    NotificationSeverity,
)
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope


async def _seed(
    *,
    audience: NotificationAudience = NotificationAudience.SUPER_ADMIN,
    audience_user_id: UUID | None = None,
    title: str = "seed",
    category: NotificationCategory = NotificationCategory.SYSTEM,
) -> AdminNotification:
    async with session_scope() as session:
        row = AdminNotification(
            org_id=uuid4(),
            category=category,
            severity=NotificationSeverity.INFO,
            title=title,
            body_md="body",
            metadata_json={},
            audience=audience,
            audience_user_id=audience_user_id,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def _create_user(
    username: str,
    password: str = "secret123",
    *,
    is_superuser: bool = False,
    is_platform_admin: bool = False,
) -> UUID:
    uid = uuid4()
    async with session_scope() as session:
        user = User(
            id=uid,
            username=username,
            password=get_password_hash(password),
            is_active=True,
            is_superuser=is_superuser,
            is_platform_admin=is_platform_admin,
        )
        session.add(user)
        await session.flush()
    return uid


async def _login(client: AsyncClient, username: str, password: str = "secret123") -> dict[str, str]:
    resp = await client.post(
        "api/v1/login", data={"username": username, "password": password}
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _delete_user(uid: UUID) -> None:
    async with session_scope() as session:
        u = await session.get(User, uid)
        if u is not None:
            await session.delete(u)


# ---------------------------------------------------------------------------
# Pure-superuser (NOT also a platform admin)
# ---------------------------------------------------------------------------


@pytest.fixture
async def super_only(client: AsyncClient):  # noqa: ARG001
    username = f"super_only_{uuid4().hex[:8]}"
    uid = await _create_user(username, is_superuser=True, is_platform_admin=False)
    yield {"id": uid, "username": username}
    await _delete_user(uid)


@pytest.fixture
async def super_only_headers(client: AsyncClient, super_only):
    return await _login(client, super_only["username"])


# ---------------------------------------------------------------------------
# Pure-platform-admin (NOT a Django/Linux superuser)
# ---------------------------------------------------------------------------


@pytest.fixture
async def platform_only(client: AsyncClient):  # noqa: ARG001
    username = f"platform_only_{uuid4().hex[:8]}"
    uid = await _create_user(username, is_superuser=False, is_platform_admin=True)
    yield {"id": uid, "username": username}
    await _delete_user(uid)


@pytest.fixture
async def platform_only_headers(client: AsyncClient, platform_only):
    return await _login(client, platform_only["username"])


# ---------------------------------------------------------------------------
# Plain org member (no admin flags)
# ---------------------------------------------------------------------------


@pytest.fixture
async def plain_member(client: AsyncClient):  # noqa: ARG001
    username = f"plain_member_{uuid4().hex[:8]}"
    uid = await _create_user(username)
    yield {"id": uid, "username": username}
    await _delete_user(uid)


@pytest.fixture
async def plain_member_headers(client: AsyncClient, plain_member):
    return await _login(client, plain_member["username"])


@pytest.fixture
async def other_member(client: AsyncClient):  # noqa: ARG001
    username = f"other_member_{uuid4().hex[:8]}"
    uid = await _create_user(username)
    yield {"id": uid, "username": username}
    await _delete_user(uid)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_super_admin_sees_super_admin_broadcasts(
    client: AsyncClient, super_only_headers
):
    row = await _seed(audience=NotificationAudience.SUPER_ADMIN, title="super-broadcast")
    resp = await client.get("api/v1/admin/notifications", headers=super_only_headers)
    assert resp.status_code == status.HTTP_200_OK
    ids = {item["id"] for item in resp.json()["items"]}
    assert str(row.id) in ids


@pytest.mark.asyncio
async def test_super_admin_does_not_see_platform_admin_broadcasts(
    client: AsyncClient, super_only_headers
):
    row = await _seed(audience=NotificationAudience.PLATFORM_ADMIN, title="platform-broadcast")
    resp = await client.get("api/v1/admin/notifications", headers=super_only_headers)
    assert resp.status_code == status.HTTP_200_OK
    ids = {item["id"] for item in resp.json()["items"]}
    assert str(row.id) not in ids


@pytest.mark.asyncio
async def test_platform_admin_sees_platform_admin_broadcasts(
    client: AsyncClient, platform_only_headers
):
    row = await _seed(audience=NotificationAudience.PLATFORM_ADMIN, title="platform-broadcast")
    resp = await client.get("api/v1/admin/notifications", headers=platform_only_headers)
    assert resp.status_code == status.HTTP_200_OK
    ids = {item["id"] for item in resp.json()["items"]}
    assert str(row.id) in ids


@pytest.mark.asyncio
async def test_platform_admin_does_not_see_super_admin_broadcasts(
    client: AsyncClient, platform_only_headers
):
    row = await _seed(audience=NotificationAudience.SUPER_ADMIN, title="super-broadcast")
    resp = await client.get("api/v1/admin/notifications", headers=platform_only_headers)
    assert resp.status_code == status.HTTP_200_OK
    ids = {item["id"] for item in resp.json()["items"]}
    assert str(row.id) not in ids


@pytest.mark.asyncio
async def test_plain_member_sees_own_targeted_row(
    client: AsyncClient, plain_member, plain_member_headers
):
    row = await _seed(
        audience=NotificationAudience.SUPER_ADMIN,  # ignored when audience_user_id is set
        audience_user_id=plain_member["id"],
        title="targeted-mine",
        category=NotificationCategory.PROFESSIONAL_SERVICES_REQUEST,
    )
    resp = await client.get("api/v1/admin/notifications", headers=plain_member_headers)
    assert resp.status_code == status.HTTP_200_OK
    items = resp.json()["items"]
    ids = {item["id"] for item in items}
    assert str(row.id) in ids


@pytest.mark.asyncio
async def test_plain_member_does_not_see_other_users_targeted_row(
    client: AsyncClient, other_member, plain_member_headers
):
    other_row = await _seed(
        audience=NotificationAudience.SUPER_ADMIN,
        audience_user_id=other_member["id"],
        title="targeted-other",
    )
    resp = await client.get("api/v1/admin/notifications", headers=plain_member_headers)
    assert resp.status_code == status.HTTP_200_OK
    ids = {item["id"] for item in resp.json()["items"]}
    assert str(other_row.id) not in ids


@pytest.mark.asyncio
async def test_plain_member_does_not_see_admin_broadcasts(
    client: AsyncClient, plain_member_headers
):
    super_row = await _seed(audience=NotificationAudience.SUPER_ADMIN, title="super-broadcast")
    plat_row = await _seed(audience=NotificationAudience.PLATFORM_ADMIN, title="platform-broadcast")
    resp = await client.get("api/v1/admin/notifications", headers=plain_member_headers)
    assert resp.status_code == status.HTTP_200_OK
    ids = {item["id"] for item in resp.json()["items"]}
    assert str(super_row.id) not in ids
    assert str(plat_row.id) not in ids


@pytest.mark.asyncio
async def test_plain_member_unread_count_only_counts_own_rows(
    client: AsyncClient, plain_member, other_member, plain_member_headers
):
    # Three rows: one mine, one other user's, one super-admin broadcast.
    await _seed(audience_user_id=plain_member["id"], title="mine")
    await _seed(audience_user_id=other_member["id"], title="theirs")
    await _seed(audience=NotificationAudience.SUPER_ADMIN, title="broadcast")
    resp = await client.get(
        "api/v1/admin/notifications/unread-count", headers=plain_member_headers
    )
    assert resp.status_code == status.HTTP_200_OK
    # We only assert "mine" is counted; can't pin the absolute number because
    # other tests sharing the in-memory DB may seed rows we can't see anyway.
    # Targeted count for plain_member must be at least 1 (the seed above).
    assert resp.json()["unread"] >= 1
    # And cannot exceed the number of rows actually addressed to this user
    # (1 from this test). In practice it equals 1 because other tests don't
    # target this user. Tighten the upper bound:
    assert resp.json()["unread"] == 1


@pytest.mark.asyncio
async def test_plain_member_can_mark_own_read(
    client: AsyncClient, plain_member, plain_member_headers
):
    row = await _seed(audience_user_id=plain_member["id"], title="mine")
    resp = await client.post(
        f"api/v1/admin/notifications/{row.id}/read", headers=plain_member_headers
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.asyncio
async def test_plain_member_cannot_mark_other_users_row_read(
    client: AsyncClient, other_member, plain_member_headers
):
    row = await _seed(audience_user_id=other_member["id"], title="theirs")
    resp = await client.post(
        f"api/v1/admin/notifications/{row.id}/read", headers=plain_member_headers
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_plain_member_cannot_mark_admin_broadcast_read(
    client: AsyncClient, plain_member_headers
):
    row = await _seed(audience=NotificationAudience.SUPER_ADMIN, title="not-mine-broadcast")
    resp = await client.post(
        f"api/v1/admin/notifications/{row.id}/read", headers=plain_member_headers
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_mark_all_read_only_affects_own_rows(
    client: AsyncClient, plain_member, other_member, plain_member_headers
):
    mine = await _seed(audience_user_id=plain_member["id"], title="mine-mark-all")
    theirs = await _seed(audience_user_id=other_member["id"], title="theirs-mark-all")
    broadcast = await _seed(audience=NotificationAudience.SUPER_ADMIN, title="broadcast-mark-all")

    resp = await client.post(
        "api/v1/admin/notifications/mark-all-read", headers=plain_member_headers
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    async with session_scope() as session:
        mine_after = await session.get(AdminNotification, mine.id)
        theirs_after = await session.get(AdminNotification, theirs.id)
        broadcast_after = await session.get(AdminNotification, broadcast.id)
    assert mine_after is not None and mine_after.read_at is not None
    assert theirs_after is not None and theirs_after.read_at is None
    assert broadcast_after is not None and broadcast_after.read_at is None

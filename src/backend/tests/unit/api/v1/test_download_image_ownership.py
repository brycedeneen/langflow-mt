"""Regression: /api/v1/files/images/{flow_id}/{file_name} must enforce ownership.

Covers CVE-2026-33484 (GHSA-7grx-3xcx-2xv5). Upstream PR #12234 was reverted
on 2026-04-15; this test asserts the Depends(get_flow) dep is back.
"""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import select

from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope


@pytest.fixture
async def two_users_with_flow():
    """Create user_a (owns flow), user_b (does not own flow)."""
    slug = uuid.uuid4().hex[:8]
    async with session_scope() as session:
        user_a = User(username=f"imga-{slug}", password=get_password_hash("testpassword"), is_active=True)
        user_b = User(username=f"imgb-{slug}", password=get_password_hash("testpassword"), is_active=True)
        session.add_all([user_a, user_b])
        await session.flush()
        flow = Flow(name=f"imgflow-{slug}", data={"nodes": [], "edges": []}, user_id=user_a.id)
        session.add(flow)
        await session.commit()
        for obj in (user_a, user_b, flow):
            await session.refresh(obj)
        ids = {
            "user_a_username": user_a.username,
            "user_b_username": user_b.username,
            "flow_id": flow.id,
        }
    yield ids
    async with session_scope() as session:
        row = await session.get(Flow, ids["flow_id"])
        if row is not None:
            await session.delete(row)
        for uname in (ids["user_a_username"], ids["user_b_username"]):
            u = (await session.exec(select(User).where(User.username == uname))).first()
            if u is not None:
                await session.delete(u)
        await session.commit()


async def _login(client, username: str) -> dict[str, str]:
    resp = await client.post("api/v1/login", data={"username": username, "password": "testpassword"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_download_image_requires_authentication(client, two_users_with_flow):
    # No auth → 401/403.
    resp = await client.get(f"api/v1/files/images/{two_users_with_flow['flow_id']}/x.png")
    assert resp.status_code in (401, 403), resp.text


async def test_download_image_denies_cross_user(client, two_users_with_flow):
    # user_b (not the flow owner) must not be able to enumerate.
    headers = await _login(client, two_users_with_flow["user_b_username"])
    resp = await client.get(
        f"api/v1/files/images/{two_users_with_flow['flow_id']}/x.png",
        headers=headers,
    )
    # 404 to match download_file's behavior (hide existence).
    assert resp.status_code == 404, resp.text

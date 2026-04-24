"""Regression tests for POST /api/v1/flows/{flow_id}/webhook-api-key.

Covers the bonus reset endpoint added on top of the 2026-04-18 secret-store plan:
authz (401/404/400 gates), the "always-generate-new" reset semantics, and
cross-org isolation.
"""

from __future__ import annotations

import uuid

import pytest

from sqlmodel import select

from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.membership.model import Membership
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope


@pytest.fixture
async def two_tenants_with_webhook_flows():
    """Two users in distinct auto-provisioned personal orgs + webhook/non-webhook flows.

    The `after_insert` user-listener at ``src/backend/base/langflow/services/database/scoping.py``
    auto-provisions a personal org + OWNER membership on every User insert. We let that
    run and attach flows to each user's auto-provisioned org — explicit Org creation in the
    fixture races the listener's SQLite CURRENT_TIMESTAMP (second precision) and produces
    flaky ``get_current_organization`` resolution when OrgA's microsecond Python timestamp
    lands in the same second as the listener's truncated timestamp.

    Layout:
      org_a (auto): user_a, flow_a_webhook (webhook=True), flow_a_no_webhook (webhook=False)
      org_b (auto): user_b, flow_b_webhook (webhook=True)
    """
    slug_a = uuid.uuid4().hex[:8]
    slug_b = uuid.uuid4().hex[:8]
    async with session_scope() as session:
        user_a = User(
            username=f"user-a-{slug_a}",
            password=get_password_hash("testpassword"),
            is_active=True,
        )
        user_b = User(
            username=f"user-b-{slug_b}",
            password=get_password_hash("testpassword"),
            is_active=True,
        )
        session.add_all([user_a, user_b])
        await session.flush()

        mem_a = (await session.exec(
            select(Membership).where(Membership.user_id == user_a.id)
        )).first()
        mem_b = (await session.exec(
            select(Membership).where(Membership.user_id == user_b.id)
        )).first()
        assert mem_a is not None, "after_insert listener must auto-provision user_a's org"
        assert mem_b is not None, "after_insert listener must auto-provision user_b's org"
        org_a_id = mem_a.organization_id
        org_b_id = mem_b.organization_id

        flow_a_webhook = Flow(
            name=f"flow-a-webhook-{slug_a}",
            data={"nodes": [], "edges": []},
            webhook=True,
            user_id=user_a.id,
            organization_id=org_a_id,
        )
        flow_a_no_webhook = Flow(
            name=f"flow-a-no-webhook-{slug_a}",
            data={"nodes": [], "edges": []},
            webhook=False,
            user_id=user_a.id,
            organization_id=org_a_id,
        )
        flow_b_webhook = Flow(
            name=f"flow-b-webhook-{slug_b}",
            data={"nodes": [], "edges": []},
            webhook=True,
            user_id=user_b.id,
            organization_id=org_b_id,
        )
        session.add_all([flow_a_webhook, flow_a_no_webhook, flow_b_webhook])
        await session.commit()
        for obj in (user_a, user_b, flow_a_webhook, flow_a_no_webhook, flow_b_webhook):
            await session.refresh(obj)
        ids = {
            "user_a_id": user_a.id,
            "user_a_username": user_a.username,
            "user_b_id": user_b.id,
            "user_b_username": user_b.username,
            "org_a_id": org_a_id,
            "org_b_id": org_b_id,
            "flow_a_webhook_id": flow_a_webhook.id,
            "flow_a_no_webhook_id": flow_a_no_webhook.id,
            "flow_b_webhook_id": flow_b_webhook.id,
        }

    yield ids

    async with session_scope() as session:
        for model, pk in [
            (Flow, ids["flow_a_webhook_id"]),
            (Flow, ids["flow_a_no_webhook_id"]),
            (Flow, ids["flow_b_webhook_id"]),
            (User, ids["user_a_id"]),
            (User, ids["user_b_id"]),
            (Organization, ids["org_a_id"]),
            (Organization, ids["org_b_id"]),
        ]:
            row = await session.get(model, pk)
            if row is not None:
                await session.delete(row)
        await session.commit()


async def _login(client, username: str) -> dict[str, str]:
    resp = await client.post(
        "api/v1/login",
        data={"username": username, "password": "testpassword"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_generate_webhook_api_key_returns_new_key(
    client, two_tenants_with_webhook_flows, in_memory_secret_store
):
    """Happy path: webhook flow in caller's org → 200 + new key stored in vault."""
    headers = await _login(client, two_tenants_with_webhook_flows["user_a_username"])
    resp = await client.post(
        f"api/v1/flows/{two_tenants_with_webhook_flows['flow_a_webhook_id']}/webhook-api-key",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "api_key" in body
    key = body["api_key"]
    assert key.startswith("ADP-APICPRO-")
    assert len(key) == len("ADP-APICPRO-") + 48

    stored_path = (
        f"{two_tenants_with_webhook_flows['org_a_id']}/webhooks/"
        f"{two_tenants_with_webhook_flows['flow_a_webhook_id']}"
    )
    stored = await in_memory_secret_store.get(stored_path)
    assert stored is not None
    assert stored["api_key"] == key
    assert "created_at" in stored


async def test_reset_invalidates_previous_key(
    client, two_tenants_with_webhook_flows, in_memory_secret_store
):
    """Each call generates a fresh key and overwrites the previous one in-vault.

    This is the key semantic difference vs `_provision_webhook_api_key`, which
    returns any existing key unchanged.
    """
    headers = await _login(client, two_tenants_with_webhook_flows["user_a_username"])
    flow_id = two_tenants_with_webhook_flows["flow_a_webhook_id"]

    first = await client.post(f"api/v1/flows/{flow_id}/webhook-api-key", headers=headers)
    assert first.status_code == 200
    key_a = first.json()["api_key"]

    second = await client.post(f"api/v1/flows/{flow_id}/webhook-api-key", headers=headers)
    assert second.status_code == 200
    key_b = second.json()["api_key"]

    assert key_a != key_b, "reset must produce a new key, not return the existing one"

    stored_path = f"{two_tenants_with_webhook_flows['org_a_id']}/webhooks/{flow_id}"
    stored = await in_memory_secret_store.get(stored_path)
    assert stored["api_key"] == key_b, "vault must hold the latest key"
    assert stored["api_key"] != key_a, "previous key must be overwritten in vault"

    # Downstream validation using the old key must now fail.
    from fastapi import HTTPException

    from langflow.api.v1.endpoints import _validate_webhook_api_key

    with pytest.raises(HTTPException) as exc_info:
        await _validate_webhook_api_key(
            org_id=str(two_tenants_with_webhook_flows["org_a_id"]),
            flow_id=str(flow_id),
            provided_key=key_a,
        )
    assert exc_info.value.status_code == 403


async def test_reset_cross_org_returns_404(
    client, two_tenants_with_webhook_flows, in_memory_secret_store  # noqa: ARG001
):
    """user_a (member of org_a only) cannot reset a key on flow_b (in org_b) → 404.

    404 (not 403) to avoid confirming the flow's existence to an unauthorized caller.
    """
    headers = await _login(client, two_tenants_with_webhook_flows["user_a_username"])
    resp = await client.post(
        f"api/v1/flows/{two_tenants_with_webhook_flows['flow_b_webhook_id']}/webhook-api-key",
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


async def test_reset_nonexistent_flow_returns_404(
    client, two_tenants_with_webhook_flows, in_memory_secret_store  # noqa: ARG001
):
    headers = await _login(client, two_tenants_with_webhook_flows["user_a_username"])
    resp = await client.post(
        f"api/v1/flows/{uuid.uuid4()}/webhook-api-key",
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


async def test_reset_flow_without_webhook_returns_400(
    client, two_tenants_with_webhook_flows, in_memory_secret_store  # noqa: ARG001
):
    """Flow exists and caller has access, but `webhook=False` → 400.

    Guards against leaking keys for flows that can't actually receive webhook traffic.
    """
    headers = await _login(client, two_tenants_with_webhook_flows["user_a_username"])
    flow_id = two_tenants_with_webhook_flows["flow_a_no_webhook_id"]
    resp = await client.post(
        f"api/v1/flows/{flow_id}/webhook-api-key",
        headers=headers,
    )
    assert resp.status_code == 400, resp.text
    assert "webhook" in resp.json()["detail"].lower()


async def test_reset_without_auth_returns_403(
    client, two_tenants_with_webhook_flows, in_memory_secret_store  # noqa: ARG001
):
    """FastAPI's default HTTPBearer returns 403 (not 401) when no credentials are provided."""
    resp = await client.post(
        f"api/v1/flows/{two_tenants_with_webhook_flows['flow_a_webhook_id']}/webhook-api-key",
    )
    assert resp.status_code == 403, resp.text

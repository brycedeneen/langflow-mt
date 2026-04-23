"""Regression: assistant.api_key must be Fernet-encrypted at rest.

Covers 2026-04-22 security finding Vuln 3.
"""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import select

from langflow.services.auth.utils import decrypt_api_key, get_password_hash
from langflow.services.database.models.membership.model import Membership
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import session_scope


@pytest.fixture
async def assistant_user():
    """Create a user and let the scoping hook auto-provision a personal org.

    We query the auto-provisioned org via membership after flush so the test
    knows exactly which org_id the endpoint's CurrentOrg resolver will pick.
    """
    slug = uuid.uuid4().hex[:8]
    async with session_scope() as session:
        user = User(
            username=f"assist-{slug}",
            password=get_password_hash("testpassword"),
            is_active=True,
        )
        session.add(user)
        await session.flush()
        # Scoping hook has inserted personal org + membership by now.
        membership = (
            await session.exec(select(Membership).where(Membership.user_id == user.id))
        ).first()
        assert membership is not None, "scoping hook failed to provision personal org"
        await session.commit()
        await session.refresh(user)
        ids = {
            "user_id": user.id,
            "username": user.username,
            "org_id": membership.organization_id,
        }
    yield ids
    async with session_scope() as session:
        for model, pk in [(User, ids["user_id"]), (Organization, ids["org_id"])]:
            row = await session.get(model, pk)
            if row is not None:
                await session.delete(row)
        await session.commit()


async def _login(client, username: str) -> dict[str, str]:
    resp = await client.post(
        "api/v1/login", data={"username": username, "password": "testpassword"}
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_assistant_api_key_stored_encrypted(client, assistant_user):
    headers = await _login(client, assistant_user["username"])
    resp = await client.put(
        "api/v1/assistant/settings",
        headers=headers,
        json={"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-plaintext-test"},
    )
    assert resp.status_code in (200, 204), resp.text

    async with session_scope() as session:
        row = (
            await session.exec(
                select(Variable).where(
                    Variable.organization_id == assistant_user["org_id"],
                    Variable.name == "assistant.api_key",
                )
            )
        ).one()
        assert row.value != "sk-plaintext-test", (
            "assistant.api_key is stored as plaintext in the Variable table"
        )
        assert row.value.startswith("gAAAAA"), (
            f"expected Fernet-encrypted value starting with 'gAAAAA', got: {row.value[:10]}"
        )
        # Round-trip through decrypt_api_key to prove the ciphertext is valid.
        assert decrypt_api_key(row.value) == "sk-plaintext-test"


async def test_assistant_settings_round_trip_decrypts(client, assistant_user):
    """After PUT, GET must surface has_key=True. The substantive guarantee is
    covered by test_assistant_api_key_stored_encrypted (decrypt round-trip)."""
    headers = await _login(client, assistant_user["username"])
    put_resp = await client.put(
        "api/v1/assistant/settings",
        headers=headers,
        json={"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-roundtrip"},
    )
    assert put_resp.status_code in (200, 204), put_resp.text

    get_resp = await client.get("api/v1/assistant/settings", headers=headers)
    assert get_resp.status_code == 200, get_resp.text
    body = get_resp.json()
    assert body["provider"] == "openai"
    assert body["model"] == "gpt-4o-mini"
    assert body["has_key"] is True

"""Regression tests: templates.py must scope by org membership.

Covers 2026-04-22 security findings Vuln 1 + Vuln 2.
"""

from __future__ import annotations

import uuid

import pytest

from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.template.model import Template
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope


@pytest.fixture
async def two_tenants():
    """Create user_a@org_a and user_b@org_b with one org-scoped template in each org."""
    slug_a = uuid.uuid4().hex[:8]
    slug_b = uuid.uuid4().hex[:8]
    async with session_scope() as session:
        org_a = Organization(name=f"OrgA-{slug_a}", slug=f"org-a-{slug_a}", is_personal=True)
        org_b = Organization(name=f"OrgB-{slug_b}", slug=f"org-b-{slug_b}", is_personal=True)
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
        session.add_all([org_a, org_b, user_a, user_b])
        await session.flush()
        session.add_all([
            Membership(user_id=user_a.id, organization_id=org_a.id, role=MembershipRole.OWNER),
            Membership(user_id=user_b.id, organization_id=org_b.id, role=MembershipRole.OWNER),
        ])
        tmpl_a = Template(
            name=f"tmpl-a-{slug_a}",
            description="org-a template",
            scope="org",
            org_id=org_a.id,
            nodes=[{"id": "n1", "data": {"node": {"template": {"k": {"value": "a-secret"}}}}}],
            edges=[],
            created_by=user_a.id,
            updated_by=user_a.id,
        )
        tmpl_b = Template(
            name=f"tmpl-b-{slug_b}",
            description="org-b template",
            scope="org",
            org_id=org_b.id,
            nodes=[{"id": "n1", "data": {"node": {"template": {"k": {"value": "b-secret"}}}}}],
            edges=[],
            created_by=user_b.id,
            updated_by=user_b.id,
        )
        session.add_all([tmpl_a, tmpl_b])
        await session.commit()
        for obj in (org_a, org_b, user_a, user_b, tmpl_a, tmpl_b):
            await session.refresh(obj)
        ids = {
            "user_a_id": user_a.id,
            "user_a_username": user_a.username,
            "user_b_id": user_b.id,
            "user_b_username": user_b.username,
            "org_a_id": org_a.id,
            "org_b_id": org_b.id,
            "tmpl_a_id": tmpl_a.id,
            "tmpl_b_id": tmpl_b.id,
        }

    yield ids

    async with session_scope() as session:
        for model, pk in [
            (Template, ids["tmpl_a_id"]),
            (Template, ids["tmpl_b_id"]),
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


async def test_list_templates_does_not_leak_other_org(client, two_tenants):
    headers = await _login(client, two_tenants["user_a_username"])
    resp = await client.get("api/v1/templates?scope=org", headers=headers)
    assert resp.status_code == 200, resp.text
    ids = {row["id"] for row in resp.json()}
    assert str(two_tenants["tmpl_a_id"]) in ids
    assert str(two_tenants["tmpl_b_id"]) not in ids, (
        "list_templates leaked an org-scoped template from a different tenant"
    )


async def test_list_templates_platform_scope_visible_across_tenants(client, two_tenants):
    # A platform-scoped template must be visible to user_a even though it was
    # created by user_b in a different org (platform templates are public-read).
    async with session_scope() as session:
        platform_tmpl = Template(
            name=f"platform-tmpl-{uuid.uuid4().hex[:8]}",
            description="platform template",
            scope="platform",
            org_id=None,
            nodes=[],
            edges=[],
            created_by=two_tenants["user_b_id"],
            updated_by=two_tenants["user_b_id"],
        )
        session.add(platform_tmpl)
        await session.commit()
        await session.refresh(platform_tmpl)
        platform_tmpl_id = platform_tmpl.id

    try:
        headers = await _login(client, two_tenants["user_a_username"])
        resp = await client.get("api/v1/templates?scope=platform", headers=headers)
        assert resp.status_code == 200, resp.text
        ids = {row["id"] for row in resp.json()}
        assert str(platform_tmpl_id) in ids
    finally:
        async with session_scope() as session:
            row = await session.get(Template, platform_tmpl_id)
            if row is not None:
                await session.delete(row)
                await session.commit()


async def test_get_template_denies_cross_org(client, two_tenants):
    headers = await _login(client, two_tenants["user_a_username"])
    resp = await client.get(
        f"api/v1/templates/{two_tenants['tmpl_b_id']}", headers=headers
    )
    # 404 (not 403) to avoid confirming the template's existence to an
    # unauthorized caller.
    assert resp.status_code == 404, resp.text


async def test_get_template_allows_own_org(client, two_tenants):
    headers = await _login(client, two_tenants["user_a_username"])
    resp = await client.get(
        f"api/v1/templates/{two_tenants['tmpl_a_id']}", headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == str(two_tenants["tmpl_a_id"])

"""Regression: the custom-component gate must reject non-admin tenants at
execution, create, upload, and template-create sites.

Covers the design at docs/superpowers/specs/2026-04-22-allow-custom-components-gate-design.md.
"""

from __future__ import annotations

import uuid

from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.membership.model import Membership
from langflow.services.database.models.organization.model import Organization
from langflow.services.deps import session_scope

from .conftest import login_as


# Any string that is NOT byte-identical to a cached shipped Component class
# source counts as "custom". The gate hashes the source verbatim, so even a
# small format change vs. a shipped class is sufficient — we use something
# unambiguous.
CUSTOM_CODE = '''
from lfx.custom import CustomComponent

class Exfiltrator(CustomComponent):
    display_name = "Exfiltrator"
    def build(self):
        return "pwned"
'''


def flow_payload_with_custom_code() -> dict:
    """Build a minimal flow payload containing one node with custom-component code.

    Kept module-top-level (not a fixture) so Tasks 5-7 can import and reuse
    the same payload when exercising the create / upload / template-create
    gates.
    """
    return {
        "nodes": [
            {
                "id": "n1",
                "data": {
                    "node": {
                        "template": {
                            "code": {"value": CUSTOM_CODE},
                        }
                    }
                },
            }
        ],
        "edges": [],
    }


async def test_execution_blocks_custom_component_for_tenant(client, tenant_and_admin):
    """Seed a flow directly in the DB with custom code, owned by the tenant.
    Attempt to build it via the SSE endpoint. The build must fail with the
    gate error."""
    async with session_scope() as session:
        flow = Flow(
            name=f"custom-exec-{uuid.uuid4().hex[:8]}",
            data=flow_payload_with_custom_code(),
            user_id=tenant_and_admin["tenant_id"],
            organization_id=tenant_and_admin["org_id"],
        )
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        flow_id = flow.id

    try:
        headers = await login_as(client, tenant_and_admin["tenant_username"])
        resp = await client.post(
            f"api/v1/build/{flow_id}/flow",
            headers=headers,
            json={"inputs": {}},
        )
        # Either the POST itself 403s, or the SSE body contains the gate error.
        assert resp.status_code in (200, 202, 403, 500), resp.text
        if resp.status_code == 403:
            assert "custom" in resp.text.lower()
        else:
            # Poll SSE events for the error (default is polling delivery).
            body = resp.text
            if "job_id" in body:
                import json as _json
                job_id = _json.loads(body)["job_id"]
                events_resp = await client.get(
                    f"api/v1/build/{job_id}/events",
                    headers=headers,
                    params={"event_delivery": "polling"},
                )
                body = events_resp.text
            # The gate raises CustomComponentNotAllowedError with a distinctive message.
            # Require the exact exception name so we don't false-positive on other
            # "custom component"-related errors from code-loading paths.
            assert "CustomComponentNotAllowedError" in body, (
                f"expected CustomComponentNotAllowedError in SSE stream, got: {body[:1500]}"
            )
    finally:
        async with session_scope() as session:
            row = await session.get(Flow, flow_id)
            if row is not None:
                await session.delete(row)
                await session.commit()


async def test_create_flow_rejects_custom_component_for_tenant(client, tenant_and_admin):
    headers = await login_as(client, tenant_and_admin["tenant_username"])
    resp = await client.post(
        "api/v1/flows/",
        headers=headers,
        json={
            "name": f"rejected-{uuid.uuid4().hex[:8]}",
            "data": flow_payload_with_custom_code(),
            "folder_id": None,
        },
    )
    assert resp.status_code == 403, resp.text
    assert "custom components are not allowed" in resp.json()["detail"].lower()


async def test_create_flow_accepts_custom_component_for_platform_admin(client, tenant_and_admin):
    # The `tenant_and_admin` fixture's admin user picks up TWO memberships: the
    # one the fixture explicitly creates (in the test org) and a personal org
    # auto-provisioned by the User `after_insert` scoping trigger. The
    # `get_current_organization` dependency prefers personal orgs and breaks
    # ties by earliest-created — which can resolve to the auto-provisioned
    # personal org, NOT the test org. When `_new_flow` then fabricates a
    # default folder via `get_or_create_default_folder(user_id)` (no org arg),
    # the folder's org gets auto-resolved by the scoping trigger from a
    # different `membership LIMIT 1` lookup, producing a folder-org/flow-org
    # mismatch. Pre-seed a folder scoped to whichever personal org the request
    # will resolve to, so the default-folder fallback picks that folder
    # (matched by `Folder.user_id == user_id`) instead of creating a new one.
    async with session_scope() as session:
        memberships = (
            await session.exec(
                select(Membership).where(Membership.user_id == tenant_and_admin["admin_id"])
            )
        ).all()
        org_ids = [m.organization_id for m in memberships]
        orgs = (await session.exec(select(Organization).where(Organization.id.in_(org_ids)))).all()
        personal_orgs = [o for o in orgs if o.is_personal]
        picked = min(personal_orgs, key=lambda o: o.created_at) if personal_orgs else min(orgs, key=lambda o: o.created_at)
        folder = Folder(
            name=DEFAULT_FOLDER_NAME,
            user_id=tenant_and_admin["admin_id"],
            organization_id=picked.id,
        )
        session.add(folder)
        await session.commit()

    headers = await login_as(client, tenant_and_admin["admin_username"])
    resp = await client.post(
        "api/v1/flows/",
        headers=headers,
        json={
            "name": f"admin-custom-{uuid.uuid4().hex[:8]}",
            "data": flow_payload_with_custom_code(),
            "folder_id": None,
        },
    )
    assert resp.status_code == 201, resp.text
    # Clean up the flow we just created.
    created_id = resp.json()["id"]
    async with session_scope() as session:
        row = await session.get(Flow, uuid.UUID(created_id))
        if row is not None:
            await session.delete(row)
            await session.commit()

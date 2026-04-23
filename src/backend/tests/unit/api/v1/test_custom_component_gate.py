"""Regression: the custom-component gate must reject non-admin tenants at
execution, create, upload, and template-create sites.

Covers the design at docs/superpowers/specs/2026-04-22-allow-custom-components-gate-design.md.
"""

from __future__ import annotations

import uuid

from langflow.services.database.models.flow.model import Flow
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

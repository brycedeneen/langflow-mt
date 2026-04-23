"""Regression: build_public_tmp must not accept a user-supplied flow graph.

Covers CVE-2026-33017 (GHSA-vwmf-pq79-vjvx). Upstream PR #12160 was reverted
on 2026-04-15; this test asserts the fix is back in place.
"""

from __future__ import annotations

import uuid

import pytest


async def test_build_public_tmp_rejects_data_param(client):
    """POSTing a `data` body to the public build endpoint must be rejected.

    FastAPI returns 422 for unknown body fields when the endpoint has no
    matching parameter, which is the desired behavior — the attacker's flow
    graph is rejected at the schema layer rather than executed.
    """
    bogus_flow_id = uuid.uuid4()
    payload = {
        "data": {
            "nodes": [
                {
                    "id": "attacker_node",
                    "data": {"node": {"template": {"code": {"value": "print('RCE')"}}}},
                }
            ],
            "edges": [],
        },
        "inputs": {},
    }
    resp = await client.post(
        f"api/v1/build_public_tmp/{bogus_flow_id}/flow",
        json=payload,
    )
    # 422 is the ideal FastAPI response when `data` is not an accepted field.
    # Any 4xx that is NOT "attacker's data was executed" is acceptable; the
    # test's core claim is that the endpoint refuses to run attacker payload.
    assert resp.status_code in (400, 403, 404, 422), resp.text
    # Belt-and-braces: make sure the response body does not contain evidence
    # that our attacker node was parsed/executed.
    assert "attacker_node" not in resp.text

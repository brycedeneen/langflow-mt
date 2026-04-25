"""End-to-end caching test through ADPToolsComponent: prove 5 tools = 1 HTTP call."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp.adp_tools import ADPToolsComponent

SAMPLE_WORKER_RESPONSE = {
    "workers": [
        {
            "associateOID": "G3ABC",
            "person": {
                "legalName": {"givenName": "Jane", "familyName1": "Doe"},
                "preferredName": {"givenName": "Janie", "familyName1": "Doe"},
                "communication": {"emails": [], "landlines": [], "mobiles": []},
            },
            "workAssignments": [],
            "workerStatus": {},
        },
    ],
}


def _make_connection():
    conn = MagicMock()
    conn.access_token = "fake-token"  # noqa: S105
    conn.api_base_url = "https://api.adp.com"
    return conn


@pytest.mark.asyncio
async def test_five_worker_tools_same_oid_one_http_call():
    """Five different agent tools on the same employee → one ADP API call.

    This is the user-visible payoff for the per-build RequestCache.
    """
    component = ADPToolsComponent()
    component.connection = _make_connection()
    component.tiles = ["Worker"]

    tools = await component.build_tools()
    by_name = {t.name: t for t in tools}

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = SAMPLE_WORKER_RESPONSE

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_worker_tools.build_mtls_httpx_client", fake_client):
        await by_name["get_employee_name"].ainvoke({"associate_oid": "G3ABC"})
        await by_name["get_employee_addresses"].ainvoke({"associate_oid": "G3ABC"})
        await by_name["get_employee_contact_information"].ainvoke({"associate_oid": "G3ABC"})
        await by_name["get_employee_job"].ainvoke({"associate_oid": "G3ABC"})
        await by_name["get_employee_compensation"].ainvoke({"associate_oid": "G3ABC"})

    assert client.request.await_count == 1


@pytest.mark.asyncio
async def test_two_oids_two_http_calls():
    """Two distinct employees → two ADP API calls (cache key includes OID)."""
    component = ADPToolsComponent()
    component.connection = _make_connection()
    component.tiles = ["Worker"]

    tools = await component.build_tools()
    by_name = {t.name: t for t in tools}

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = SAMPLE_WORKER_RESPONSE

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_worker_tools.build_mtls_httpx_client", fake_client):
        await by_name["get_employee_name"].ainvoke({"associate_oid": "G3ABC"})
        await by_name["get_employee_compensation"].ainvoke({"associate_oid": "G3ABC"})
        await by_name["get_employee_name"].ainvoke({"associate_oid": "G3XYZ"})
        await by_name["get_employee_compensation"].ainvoke({"associate_oid": "G3XYZ"})

    assert client.request.await_count == 2

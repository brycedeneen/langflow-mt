"""Tests that the legacy admin template-metadata routes have been removed."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_metadata_templates_routes_removed(
    client: AsyncClient, logged_in_headers_super_user
):
    headers = logged_in_headers_super_user
    res = await client.get("/api/v1/admin/metadata/templates", headers=headers)
    assert res.status_code == 404

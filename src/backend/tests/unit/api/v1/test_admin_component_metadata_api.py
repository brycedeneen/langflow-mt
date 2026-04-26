"""Integration tests for admin component metadata endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.database.models import ComponentMetadata
from langflow.services.deps import session_scope


@pytest.mark.asyncio
async def test_list_components_includes_live_and_orphan_rows(
    client: AsyncClient, logged_in_headers_super_user, active_super_user
):
    # Seed an orphan row using the same async session pattern as other tests in
    # this directory — match the Task 7 style (session_scope()).
    async with session_scope() as session:
        session.add(
            ComponentMetadata(
                component_name="DoesNotExistYet",
                agent_summary="Staged.",
                updated_by=active_super_user.id,
            )
        )
        await session.commit()

    response = await client.get(
        "/api/v1/admin/metadata/components", headers=logged_in_headers_super_user
    )
    assert response.status_code == 200
    rows = response.json()
    by_name = {r["component_name"]: r for r in rows}

    # Live component that ships with the catalog
    assert "Webhook" in by_name, "Live catalog must include Webhook"
    assert by_name["Webhook"]["is_orphan"] is False
    assert by_name["Webhook"]["display_name"] is not None

    # Orphan row
    assert "DoesNotExistYet" in by_name
    assert by_name["DoesNotExistYet"]["is_orphan"] is True


@pytest.mark.asyncio
async def test_put_component_creates_row(
    client: AsyncClient, logged_in_headers_super_user
):
    response = await client.put(
        "/api/v1/admin/metadata/components/Webhook",
        headers=logged_in_headers_super_user,
        json={"agent_summary": "Inbound webhook receiver.", "agent_usage_notes": "..."},
    )
    assert response.status_code == 200
    assert response.json()["agent_summary"] == "Inbound webhook receiver."

    async with session_scope() as session:
        row = (
            await session.exec(
                select(ComponentMetadata).where(ComponentMetadata.component_name == "Webhook")
            )
        ).one_or_none()
        assert row is not None


@pytest.mark.asyncio
async def test_delete_component_removes_orphan(
    client: AsyncClient, logged_in_headers_super_user, active_super_user
):
    async with session_scope() as session:
        session.add(
            ComponentMetadata(component_name="DeadName", updated_by=active_super_user.id)
        )
        await session.commit()

    response = await client.delete(
        "/api/v1/admin/metadata/components/DeadName",
        headers=logged_in_headers_super_user,
    )
    assert response.status_code == 204

    async with session_scope() as session:
        rows = (
            await session.exec(
                select(ComponentMetadata).where(ComponentMetadata.component_name == "DeadName")
            )
        ).all()
        assert rows == []


@pytest.mark.asyncio
async def test_components_endpoint_requires_superuser(
    client: AsyncClient, logged_in_headers
):
    response = await client.get(
        "/api/v1/admin/metadata/components", headers=logged_in_headers
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_buckets_class_name_row_under_canonical_key(
    client: AsyncClient, logged_in_headers_super_user, active_super_user
):
    """A row keyed by a Python class name (legacy) must not appear as an orphan when a
    live component exists at its canonical registry key."""
    async with session_scope() as session:
        session.add(
            ComponentMetadata(
                component_name="WebhookComponent",
                agent_summary="Class-name keyed.",
                updated_by=None,
            )
        )
        await session.commit()

    try:
        response = await client.get(
            "/api/v1/admin/metadata/components", headers=logged_in_headers_super_user
        )
        assert response.status_code == 200
        rows = response.json()
        by_name = {r["component_name"]: r for r in rows}

        # The class-name alias resolves to the registry key, so the row appears
        # under "Webhook" with the metadata merged and is_orphan=False.
        assert "Webhook" in by_name
        assert by_name["Webhook"]["is_orphan"] is False
        assert by_name["Webhook"]["metadata"]["agent_summary"] == "Class-name keyed."

        # The class-name spelling must not appear as a separate row.
        assert "WebhookComponent" not in by_name
    finally:
        async with session_scope() as session:
            for name in ("WebhookComponent", "Webhook"):
                row = (
                    await session.exec(
                        select(ComponentMetadata).where(
                            ComponentMetadata.component_name == name
                        )
                    )
                ).one_or_none()
                if row:
                    await session.delete(row)
            await session.commit()


@pytest.mark.asyncio
async def test_put_resolves_class_name_alias(
    client: AsyncClient, logged_in_headers_super_user
):
    """PUT against a class-name alias writes the row keyed by the canonical registry key."""
    response = await client.put(
        "/api/v1/admin/metadata/components/WebhookComponent",
        headers=logged_in_headers_super_user,
        json={"agent_summary": "via alias", "agent_usage_notes": "n"},
    )
    assert response.status_code == 200

    try:
        async with session_scope() as session:
            canonical = (
                await session.exec(
                    select(ComponentMetadata).where(
                        ComponentMetadata.component_name == "Webhook"
                    )
                )
            ).one_or_none()
            aliased = (
                await session.exec(
                    select(ComponentMetadata).where(
                        ComponentMetadata.component_name == "WebhookComponent"
                    )
                )
            ).one_or_none()
        assert canonical is not None
        assert canonical.agent_summary == "via alias"
        assert aliased is None, "PUT must not write under the class-name alias."
    finally:
        async with session_scope() as session:
            for name in ("WebhookComponent", "Webhook"):
                row = (
                    await session.exec(
                        select(ComponentMetadata).where(
                            ComponentMetadata.component_name == name
                        )
                    )
                ).one_or_none()
                if row:
                    await session.delete(row)
            await session.commit()

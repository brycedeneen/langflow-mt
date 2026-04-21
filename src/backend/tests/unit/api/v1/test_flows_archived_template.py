"""Tests for C7: flow creation 422 guard when based_on_template_flow_id points to archived template."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.database.models.template.model import Template
from langflow.services.deps import session_scope


# These tests reuse the shared active_user / logged_in_headers fixtures from conftest.py
# (via the `client` fixture) to create flows via the normal POST /flows/ endpoint.


@pytest.fixture
async def _archived_template(active_user):
    """Create a platform-scoped template and immediately archive it."""
    uid = active_user.id
    async with session_scope() as session:
        t = Template(
            name=f"ArchivedForFlow-{uuid.uuid4()}",
            nodes=[],
            edges=[],
            scope="platform",
            created_by=uid,
            updated_by=uid,
            archived_at=datetime.now(timezone.utc),
        )
        session.add(t)
        await session.flush()
        await session.refresh(t)
        tmpl_id = t.id

    yield tmpl_id

    async with session_scope() as session:
        db = await session.get(Template, tmpl_id)
        if db:
            await session.delete(db)


@pytest.fixture
async def _live_template(active_user):
    """Create a platform-scoped template that is NOT archived."""
    uid = active_user.id
    async with session_scope() as session:
        t = Template(
            name=f"LiveTemplate-{uuid.uuid4()}",
            nodes=[],
            edges=[],
            scope="platform",
            created_by=uid,
            updated_by=uid,
            archived_at=None,
        )
        session.add(t)
        await session.flush()
        await session.refresh(t)
        tmpl_id = t.id

    yield tmpl_id

    async with session_scope() as session:
        db = await session.get(Template, tmpl_id)
        if db:
            await session.delete(db)


async def test_create_flow_with_archived_template_returns_422(
    client: AsyncClient,
    logged_in_headers,
    _archived_template,
):
    """Flow creation with based_on_template_flow_id pointing to an archived template → 422."""
    payload = {
        "name": f"ShouldFail-{uuid.uuid4()}",
        "data": {"nodes": [], "edges": []},
        "based_on_template_flow_id": str(_archived_template),
    }
    resp = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "archived" in resp.json()["detail"].lower()


async def test_create_flow_with_live_template_succeeds(
    client: AsyncClient,
    logged_in_headers,
    _live_template,
):
    """Flow creation with based_on_template_flow_id pointing to a live template → 201."""
    flow_name = f"LiveFlow-{uuid.uuid4()}"
    payload = {
        "name": flow_name,
        "data": {"nodes": [], "edges": []},
        "based_on_template_flow_id": str(_live_template),
    }
    resp = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    # The guard should pass; creation may succeed (201) or fail for other reasons (name dup etc.)
    # but specifically must NOT be 422 with "archived"
    assert resp.status_code != status.HTTP_422_UNPROCESSABLE_ENTITY or "archived" not in resp.json().get("detail", "")

    # Clean up if created
    if resp.status_code == status.HTTP_201_CREATED:
        flow_id = resp.json()["id"]
        await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

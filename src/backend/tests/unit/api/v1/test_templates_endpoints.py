"""Endpoint tests for /api/v1/templates CRUD router (Phase 1)."""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.template.model import Template
from langflow.services.deps import session_scope


@pytest.fixture(autouse=True)
async def _cleanup_templates_created_during_test():
    """Delete any Template rows created by the test so the superuser fixture teardown
    (which cascades User delete) isn't blocked by template.created_by RESTRICT FK."""
    async with session_scope() as session:
        before = {
            tid
            for (tid,) in (
                await session.exec(select(Template.id))
            )
        }
    yield
    async with session_scope() as session:
        rows = (await session.exec(select(Template))).all()
        for row in rows:
            if row.id not in before:
                await session.delete(row)


@pytest.fixture
async def sample_flow(active_super_user):
    async with session_scope() as session:
        flow = Flow(
            name=f"Source Flow {uuid.uuid4()}",
            data={"nodes": [], "edges": []},
            user_id=active_super_user.id,
        )
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        flow_id = flow.id

    yield flow

    async with session_scope() as session:
        db_flow = await session.get(Flow, flow_id)
        if db_flow is not None:
            await session.delete(db_flow)


@pytest.fixture
async def flow_with_secret_field(active_super_user):
    async with session_scope() as session:
        flow = Flow(
            name=f"Secret Flow {uuid.uuid4()}",
            data={
                "nodes": [
                    {
                        "id": "Agent-1",
                        "data": {
                            "node": {
                                "template": {
                                    "api_key": {"value": "sk-xyz", "password": True},
                                    "instructions": {"value": "do thing", "password": False},
                                }
                            }
                        },
                    }
                ],
                "edges": [],
            },
            user_id=active_super_user.id,
        )
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        flow_id = flow.id

    yield flow

    async with session_scope() as session:
        db_flow = await session.get(Flow, flow_id)
        if db_flow is not None:
            await session.delete(db_flow)


@pytest.fixture
async def sample_template(active_super_user):
    async with session_scope() as session:
        template = Template(
            name=f"Sample-{uuid.uuid4()}",
            description="sample",
            nodes=[],
            edges=[],
            created_by=active_super_user.id,
            updated_by=active_super_user.id,
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)
        template_id = template.id

    yield template

    async with session_scope() as session:
        db_template = await session.get(Template, template_id)
        if db_template is not None:
            await session.delete(db_template)


async def test_post_template_as_superuser_succeeds(client, logged_in_headers_super_user, sample_flow):
    resp = await client.post(
        "api/v1/templates",
        json={
            "source_flow_id": str(sample_flow.id),
            "name": f"My Template {uuid.uuid4()}",
            "description": "A test template",
            "blanked_fields": [],
        },
        headers=logged_in_headers_super_user,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "nodes" in body
    assert "edges" in body


async def test_post_template_as_regular_user_forbidden(client, logged_in_headers, sample_flow):
    resp = await client.post(
        "api/v1/templates",
        json={"source_flow_id": str(sample_flow.id), "name": f"x-{uuid.uuid4()}"},
        headers=logged_in_headers,
    )
    assert resp.status_code == 403


async def test_post_template_duplicate_name_returns_409(client, logged_in_headers_super_user, sample_flow):
    name = f"Dup-{uuid.uuid4()}"
    body = {"source_flow_id": str(sample_flow.id), "name": name}
    resp1 = await client.post("api/v1/templates", json=body, headers=logged_in_headers_super_user)
    assert resp1.status_code == 201, resp1.text
    resp2 = await client.post("api/v1/templates", json=body, headers=logged_in_headers_super_user)
    assert resp2.status_code == 409


async def test_post_template_blanks_password_fields_unconditionally(
    client, logged_in_headers_super_user, flow_with_secret_field
):
    resp = await client.post(
        "api/v1/templates",
        json={
            "source_flow_id": str(flow_with_secret_field.id),
            "name": f"secret-free-{uuid.uuid4()}",
            "blanked_fields": [],
        },
        headers=logged_in_headers_super_user,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # Find the node whose input is password=True; its value must be empty.
    for node in body["nodes"]:
        tmpl = node.get("data", {}).get("node", {}).get("template", {})
        for _field_name, cfg in tmpl.items():
            if cfg.get("password") is True:
                assert cfg.get("value") in ("", None)


async def test_put_template_overwrites_content(client, logged_in_headers_super_user, sample_flow, sample_template):
    resp = await client.put(
        f"api/v1/templates/{sample_template.id}",
        json={
            "source_flow_id": str(sample_flow.id),
            "name": sample_template.name,
            "description": "new description",
            "blanked_fields": [],
        },
        headers=logged_in_headers_super_user,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["description"] == "new description"


async def test_delete_template_soft_deletes(client, logged_in_headers_super_user, sample_template):
    resp = await client.delete(
        f"api/v1/templates/{sample_template.id}",
        headers=logged_in_headers_super_user,
    )
    assert resp.status_code == 204

    get_resp = await client.get(
        f"api/v1/templates/{sample_template.id}",
        headers=logged_in_headers_super_user,
    )
    assert get_resp.status_code == 404

    list_resp = await client.get("api/v1/templates", headers=logged_in_headers_super_user)
    ids = [t["id"] for t in list_resp.json()]
    assert str(sample_template.id) not in ids


async def test_get_list_returns_slim_payload(client, logged_in_headers_super_user, sample_template):
    resp = await client.get("api/v1/templates", headers=logged_in_headers_super_user)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    first = next(t for t in items if t["id"] == str(sample_template.id))
    assert "nodes" not in first
    assert "edges" not in first


async def test_get_detail_returns_full_payload(client, logged_in_headers_super_user, sample_template):
    resp = await client.get(
        f"api/v1/templates/{sample_template.id}",
        headers=logged_in_headers_super_user,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "nodes" in body
    assert "edges" in body


async def test_post_template_tolerates_non_dict_field_configs(
    client, logged_in_headers_super_user, active_super_user
):
    """Legacy flow data sometimes stores non-dict values under node.data.node.template.
    The blanking helper must pass those through unchanged rather than crash."""
    async with session_scope() as session:
        flow = Flow(
            name=f"Legacy-{uuid.uuid4()}",
            data={
                "nodes": [
                    {
                        "id": "N-1",
                        "data": {
                            "node": {
                                "template": {
                                    "_type": "CustomComponent",  # str, not dict
                                    "code": None,  # None
                                    "normal_field": {"value": "keep", "password": False},
                                }
                            }
                        },
                    }
                ],
                "edges": [],
            },
            user_id=active_super_user.id,
        )
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        flow_id = flow.id

    resp = await client.post(
        "api/v1/templates",
        json={
            "source_flow_id": str(flow_id),
            "name": f"legacy-ok-{uuid.uuid4()}",
            "blanked_fields": [],
        },
        headers=logged_in_headers_super_user,
    )
    assert resp.status_code == 201, resp.text
    tmpl = resp.json()["nodes"][0]["data"]["node"]["template"]
    assert tmpl["_type"] == "CustomComponent"
    assert tmpl["code"] is None
    assert tmpl["normal_field"]["value"] == "keep"

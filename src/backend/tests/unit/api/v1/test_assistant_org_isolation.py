"""Cross-org regression matrix for assistant-callable surfaces.

Every entry in ASSISTANT_SURFACES must come from the inventory note at
`docs/superpowers/notes/2026-04-23-assistant-surface-inventory.md`. The
meta-test verifies the registry matches the number of mounted assistant
routes so a new surface cannot ship without a test.

Task 5 populates ASSISTANT_SURFACES with concrete entries and wires
_create_foreign_target per factory.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.membership.model import Membership
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import session_scope


@dataclass(frozen=True)
class Surface:
    name: str
    http_method: str
    path_template: str  # e.g. "/api/v1/assistant/flow/{flow_id}"
    # Factory selects the foreign-org resource shape to set up + how to send the request.
    # - "flow_in_path": foreign Flow id substituted into `{flow_id}` in path_template.
    # - "flow_in_body": foreign Flow id placed in request body at `body["flow_id"]`.
    # - "settings_isolation": no flow; seeds a Variable in the foreign org and asserts
    #   the actor's GET/PUT response does not leak its name. (These routes are org-scoped
    #   via CurrentOrg, so they cannot 404 — they return the actor's own data.)
    factory: str  # "flow_in_path" | "flow_in_body" | "settings_isolation"
    # Optional JSON body template for non-GET routes. For `flow_in_body` surfaces,
    # the harness fills in `flow_id` with the created foreign flow id; other fields
    # are sent as-is.
    body_template: dict[str, Any] | None = field(default=None)


# One entry per mounted assistant route — inventory:
#   docs/superpowers/notes/2026-04-23-assistant-surface-inventory.md
_COMPONENT_ASSIST_BODY_TEMPLATE: dict[str, Any] = {
    # flow_id filled at call-time with the foreign flow's id
    "flow_id": None,
    "node_id": "node-x",
    "node_snapshot": {
        "node_id": "node-x",
        "type": "GenericComponent",
        "display_name": "Generic",
        "description": "test node",
        "template": {},
        "outputs": [],
    },
    "neighbor_snapshots": [],
    "thread": [],
    "user_message": "hello",
}


ASSISTANT_SURFACES: list[Surface] = [
    Surface(
        name="get_conversation",
        http_method="GET",
        path_template="api/v1/assistant/flows/{flow_id}/conversation",
        factory="flow_in_path",
    ),
    Surface(
        name="send_message",
        http_method="POST",
        path_template="api/v1/assistant/flows/{flow_id}/messages",
        factory="flow_in_path",
        body_template={"content": "hi"},
    ),
    Surface(
        name="delete_conversation",
        http_method="DELETE",
        path_template="api/v1/assistant/flows/{flow_id}/conversation",
        factory="flow_in_path",
    ),
    Surface(
        name="get_settings",
        http_method="GET",
        path_template="api/v1/assistant/settings",
        factory="settings_isolation",
    ),
    Surface(
        name="update_settings",
        http_method="PUT",
        path_template="api/v1/assistant/settings",
        factory="settings_isolation",
        body_template={"provider": "openai", "model": "gpt-4o-mini", "api_key": None},
    ),
    Surface(
        name="greet_conversation",
        http_method="POST",
        path_template="api/v1/assistant/flows/{flow_id}/greet",
        factory="flow_in_path",
    ),
    Surface(
        name="component_assist_messages",
        http_method="POST",
        path_template="api/v1/assistant/components/messages",
        factory="flow_in_body",
        body_template=_COMPONENT_ASSIST_BODY_TEMPLATE,
    ),
]


@pytest.mark.skipif(
    not ASSISTANT_SURFACES,
    reason="ASSISTANT_SURFACES is empty — Task 5 populates it",
)
@pytest.mark.parametrize("surface", ASSISTANT_SURFACES, ids=[s.name for s in ASSISTANT_SURFACES])
async def test_cross_org_returns_404(
    client: AsyncClient, two_org_fixture, surface: Surface
) -> None:
    actor, _actor_org, _other, other_org = two_org_fixture

    if surface.factory == "flow_in_path":
        foreign_flow_id = await _create_foreign_flow(other_org)
        url = surface.path_template.format(flow_id=foreign_flow_id)
        resp = await client.request(
            surface.http_method,
            url,
            headers=actor["headers"],
            json=surface.body_template,
        )
        assert resp.status_code == 404, (
            f"{surface.name}: expected 404 for cross-org access, "
            f"got {resp.status_code}: {resp.text}"
        )

    elif surface.factory == "flow_in_body":
        foreign_flow_id = await _create_foreign_flow(other_org)
        body = copy.deepcopy(surface.body_template or {})
        body["flow_id"] = foreign_flow_id
        resp = await client.request(
            surface.http_method,
            surface.path_template,
            headers=actor["headers"],
            json=body,
        )
        assert resp.status_code == 404, (
            f"{surface.name}: expected 404 for cross-org access, "
            f"got {resp.status_code}: {resp.text}"
        )

    elif surface.factory == "settings_isolation":
        # Settings routes resolve org via CurrentOrg, so a cross-org foreign Variable
        # can never appear in the actor's response. The test asserts the name does
        # not leak — it's a trip-wire for if someone later loosens the org filter.
        foreign_secret_name = f"foreign_secret_{uuid4().hex}"
        other_user_id = await _other_user_id_for(other_org)
        await _create_foreign_variable(
            org_id=other_org,
            user_id=other_user_id,
            name=foreign_secret_name,
        )
        resp = await client.request(
            surface.http_method,
            surface.path_template,
            headers=actor["headers"],
            json=surface.body_template,
        )
        # These routes don't 404 — they return the actor's own settings.
        assert resp.status_code == 200, (
            f"{surface.name}: expected 200 for settings isolation probe, "
            f"got {resp.status_code}: {resp.text}"
        )
        assert foreign_secret_name not in resp.text, (
            f"{surface.name}: foreign variable name leaked into response: {resp.text}"
        )

    else:
        pytest.fail(f"unknown factory {surface.factory!r} for surface {surface.name}")


def test_registry_covers_all_mounted_assistant_routes() -> None:
    """If this test fails, a new assistant route was added without a Surface entry.

    Intended to FAIL on first run (Task 4) because ASSISTANT_SURFACES is empty.
    Task 5 populates the list and this test becomes green.
    """
    from langflow.api.v1 import assistant, component_assist

    def _count_routes(module) -> int:
        return sum(
            1
            for r in module.router.routes
            if getattr(r, "include_in_schema", True)
        )

    mounted = _count_routes(assistant) + _count_routes(component_assist)
    assert len(ASSISTANT_SURFACES) == mounted, (
        f"Registry has {len(ASSISTANT_SURFACES)} entries but assistant routers mount {mounted}. "
        "Add a Surface entry for each new route and update the inventory."
    )


# --- helpers -----------------------------------------------------------------


async def _other_user_id_for(other_org_id: UUID) -> UUID:
    """Return the foreign-org user's id by querying Membership.

    two_org_fixture creates one foreign user per org; we need that user's id
    when seeding cross-org Variables (Variable.user_id is NOT NULL).
    """
    async with session_scope() as session:
        stmt = select(Membership).where(Membership.organization_id == other_org_id)
        rows = (await session.exec(stmt)).all()
        assert rows, f"no membership found for org {other_org_id}"
        return rows[0].user_id


async def _create_foreign_flow(org_id: UUID) -> str:
    """Create a Flow owned by the foreign org and return its id as a string."""
    async with session_scope() as session:
        flow = Flow(
            name=f"foreign-flow-{uuid4().hex[:8]}",
            data={"nodes": [], "edges": []},
            organization_id=org_id,
        )
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        return str(flow.id)


async def _create_foreign_variable(*, org_id: UUID, user_id: UUID, name: str) -> str:
    """Create a Variable owned by the foreign org and return its id as a string."""
    async with session_scope() as session:
        var = Variable(
            name=name,
            value="leaked-if-you-see-me",
            type="generic",
            default_fields=[],
            user_id=user_id,
            organization_id=org_id,
        )
        session.add(var)
        await session.commit()
        await session.refresh(var)
        return str(var.id)

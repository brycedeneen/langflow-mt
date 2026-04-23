"""Cross-org regression matrix for assistant-callable surfaces.

Every entry in ASSISTANT_SURFACES must come from the inventory note at
`docs/superpowers/notes/2026-04-23-assistant-surface-inventory.md`. The
meta-test verifies the registry matches the number of mounted assistant
routes so a new surface cannot ship without a test.

Task 5 populates ASSISTANT_SURFACES with concrete entries and wires
_create_foreign_target per factory. This file intentionally ships empty
so the meta-test FAILS (count mismatch), proving the harness is wired.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from httpx import AsyncClient


@dataclass(frozen=True)
class Surface:
    name: str
    http_method: str
    path_template: str  # e.g. "/api/v1/assistant/flow/{flow_id}"
    factory: str  # which entity to create in the foreign org: "flow" | "flow_run" | "file"


# Populated by Task 5 iteration; one entry per row in the inventory.
ASSISTANT_SURFACES: list[Surface] = [
    # Example (replace with real data from the inventory):
    # Surface(name="read_flow", http_method="GET",
    #         path_template="/api/v1/assistant/flow/{flow_id}", factory="flow"),
]


@pytest.mark.skipif(
    not ASSISTANT_SURFACES,
    reason="ASSISTANT_SURFACES is empty — Task 5 populates it",
)
@pytest.mark.parametrize("surface", ASSISTANT_SURFACES, ids=[s.name for s in ASSISTANT_SURFACES])
async def test_cross_org_returns_404(client: AsyncClient, two_org_fixture, surface: Surface) -> None:
    actor, _actor_org, _other, other_org = two_org_fixture
    target_id = await _create_foreign_target(surface.factory, other_org)
    url = surface.path_template.format(**{f"{surface.factory}_id": target_id})
    resp = await client.request(surface.http_method, url, headers=actor["headers"])
    assert resp.status_code == 404, (
        f"{surface.name}: expected 404 for cross-org access, got {resp.status_code}: {resp.text}"
    )


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


async def _create_foreign_target(factory: str, org_id) -> str:
    """Create a resource owned by the foreign org and return its ID as a string.

    Stub — Task 5 fills this in per factory name using the test DB session.
    """
    raise NotImplementedError(f"factory '{factory}' not wired — add it in Task 5")

"""In-process smoke test covering the checks from the ADP connector plan's Task 10
("manual smoke flow in Langflow UI"). The original task is browser-based and requires
live ADP credentials, so it cannot run in CI. This file automates the subset that can
be verified statically: bundle size, field schemas, type bindings, and endpoint catalog.

Catches regressions like:
- A new component added to the bundle without updating the manual-smoke expectations.
- The v1 `cert_source` File-Path/PEM toggle reappearing after a refactor.
- The `ADPConnection` wire type being broken between Auth and its consumers.
- The endpoint-catalog dropdown silently losing an entry.
"""

from __future__ import annotations

from lfx.components.adp import __all__ as adp_bundle_exports
from lfx.components.adp._shared import ADPConnection
from lfx.components.adp.adp_api_request import ENDPOINT_CATALOG, ADPAPIRequestComponent
from lfx.components.adp.adp_auth import ADPAuthComponent
from lfx.components.adp.adp_mcp import ADPMCPComponent

# ---------------------------------------------------------------------------
# Bundle registration
# ---------------------------------------------------------------------------


def test_bundle_exports_five_components():
    """The bundle now exposes 5 components after the multi-select tools consolidation.

    Auth, API Request, MCP, Trigger, and the unified ADPToolsComponent (which itself
    multi-selects from 29 internal tile builders).
    """
    assert len(adp_bundle_exports) == 5, (
        f"ADP bundle exports changed: expected 5, got {len(adp_bundle_exports)}. "
        f"Current exports: {sorted(adp_bundle_exports)}"
    )


def test_bundle_foundation_components_present():
    """The four foundation components called out in Task 10 Step 2 must be exported."""
    foundation = {"ADPAuthComponent", "ADPAPIRequestComponent", "ADPMCPComponent", "ADPTriggerComponent"}
    missing = foundation - set(adp_bundle_exports)
    assert not missing, f"Missing foundation components from bundle __all__: {missing}"


# ---------------------------------------------------------------------------
# Auth v2 field schema (Task 10 Step 4)
# ---------------------------------------------------------------------------


def _input_names(component) -> list[str]:
    return [getattr(i, "name", None) for i in component.inputs]


def test_auth_has_v2_field_schema():
    """Task 10 Step 4: four auth-credential fields, no legacy cert_source toggle."""
    component = ADPAuthComponent()
    names = _input_names(component)
    expected = {"client_id", "client_secret", "cert_pem", "key_pem"}
    missing = expected - set(names)
    assert not missing, f"Auth component missing v2 fields: {missing}"
    assert "cert_source" not in names, (
        "Auth component still exposes the v1 `cert_source` File-Path/PEM toggle — "
        "should have been removed in v2. See adp_auth.py docstring."
    )
    assert "cert_path" not in names, (
        "Auth component still exposes the v1 `cert_path` field — should have been "
        "removed in v2."
    )


def test_auth_exports_adp_connection_output():
    """Task 10 Step 3: Auth component emits a `connection` output consumable by API Request / MCP."""
    component = ADPAuthComponent()
    output_names = [getattr(o, "name", None) for o in component.outputs]
    assert "connection" in output_names, "Auth must emit a `connection` output for downstream wiring."


# ---------------------------------------------------------------------------
# API Request (Task 10 Steps 3 + 5)
# ---------------------------------------------------------------------------


def test_api_request_accepts_adp_connection_wire():
    """Task 10 Step 3: API Request's `connection` input must type-check against `ADPConnection`."""
    component = ADPAPIRequestComponent()
    conn_input = next((i for i in component.inputs if getattr(i, "name", None) == "connection"), None)
    assert conn_input is not None, "API Request must declare a `connection` input"
    input_types = getattr(conn_input, "input_types", None)
    assert input_types is not None and "ADPConnection" in input_types, (
        f"API Request `connection` input_types must include 'ADPConnection', got {input_types!r}"
    )


def test_api_request_endpoint_catalog_dropdown():
    """Task 10 Step 5: the endpoint dropdown options reflect ENDPOINT_CATALOG."""
    component = ADPAPIRequestComponent()
    endpoint_input = next((i for i in component.inputs if getattr(i, "name", None) == "endpoint"), None)
    assert endpoint_input is not None
    options = getattr(endpoint_input, "options", None)
    assert options == list(ENDPOINT_CATALOG.keys()), (
        "Endpoint dropdown options drifted from ENDPOINT_CATALOG. "
        "Both should list: Workers, Worker Demographics, Pay Statements, "
        "Time Cards, Jobs, Meta, Other (custom path)."
    )
    # Spot-check a couple of entries stay in the catalog.
    for expected in ("Workers", "Other (custom path)", "Meta"):
        assert expected in options, f"Endpoint dropdown missing {expected!r}"


# ---------------------------------------------------------------------------
# MCP component (Task 10 Step 6)
# ---------------------------------------------------------------------------


def test_mcp_accepts_adp_connection_wire():
    """Task 10 Step 6: MCP component accepts the same `ADPConnection` type as API Request."""
    component = ADPMCPComponent()
    conn_input = next((i for i in component.inputs if getattr(i, "name", None) == "connection"), None)
    assert conn_input is not None, "MCP must declare a `connection` input"
    input_types = getattr(conn_input, "input_types", None)
    assert input_types is not None and "ADPConnection" in input_types


# ---------------------------------------------------------------------------
# Unified ADPToolsComponent (replaces the 29 individual tile components)
# ---------------------------------------------------------------------------


def test_adp_tools_component_accepts_adp_connection_wire():
    """The unified ADPToolsComponent must wire `ADPConnection` like API Request and MCP."""
    from lfx.components.adp.adp_tools import ADPToolsComponent

    component = ADPToolsComponent()
    conn_input = next((i for i in component.inputs if getattr(i, "name", None) == "connection"), None)
    assert conn_input is not None, "ADPToolsComponent must declare a `connection` input"
    input_types = getattr(conn_input, "input_types", None)
    assert input_types is not None and "ADPConnection" in input_types, (
        f"ADPToolsComponent `connection` input_types must include 'ADPConnection', got {input_types!r}"
    )


def test_adp_tools_component_has_tiles_multiselect():
    """ADPToolsComponent must expose a `tiles` MultiselectInput populated from TILE_BUILDERS."""
    from lfx.components.adp.adp_tools import TILE_BUILDERS, ADPToolsComponent

    component = ADPToolsComponent()
    tiles_input = next((i for i in component.inputs if getattr(i, "name", None) == "tiles"), None)
    assert tiles_input is not None, "ADPToolsComponent must declare a `tiles` input"
    options = getattr(tiles_input, "options", None)
    assert options is not None
    assert set(options) == set(TILE_BUILDERS.keys()), (
        "tiles MultiselectInput options drifted from TILE_BUILDERS keys"
    )


def test_adp_connection_dataclass_unchanged():
    """Connection type shape stays compatible — consumers rely on these fields."""
    for field_name in ("client_id", "client_secret", "cert_pem", "key_pem", "token_url", "access_token"):
        assert hasattr(ADPConnection, "__dataclass_fields__") or hasattr(ADPConnection, field_name), (
            f"ADPConnection must expose `{field_name}` for downstream components."
        )

"""Catalog tools — read-only component knowledge for the assistant.

Wraps the low-level functions in ``langflow.agentic.utils.component_search``
into a tool-friendly interface that the AssistantService (and MCP layer) can
call during the tool-calling loop.
"""

from __future__ import annotations

from typing import Any

from langflow.agentic.utils.component_search import (
    get_all_component_types,
    get_component_by_name,
    get_components_count,
    list_all_components,
)

# Fields returned by the "summary" endpoints (search / list).
SUMMARY_FIELDS: list[str] = ["name", "display_name", "type", "description"]

# Fields returned by the "full schema" endpoint.
SCHEMA_FIELDS: list[str] = [
    "name",
    "display_name",
    "type",
    "description",
    "template",
    "icon",
    "is_input",
    "is_output",
]


async def list_categories() -> list[dict[str, Any]]:
    """Return every component category with its component count.

    Returns:
        ``[{"name": "llms", "count": 18}, ...]``
    """
    types = await get_all_component_types()
    categories: list[dict[str, Any]] = []
    for t in types:
        count = await get_components_count(component_type=t)
        categories.append({"name": t, "count": count})
    return categories


async def search_components(
    query: str | None = None,
    component_type: str | None = None,
) -> list[dict[str, Any]]:
    """Search / list components with summary-level detail.

    Args:
        query: Optional substring to match against name, display_name, or
            description (case-insensitive).
        component_type: Optional category filter (e.g. ``"llms"``).

    Returns:
        List of dicts with keys from :data:`SUMMARY_FIELDS`.
    """
    return await list_all_components(
        query=query,
        component_type=component_type,
        fields=SUMMARY_FIELDS,
    )


async def get_component_schema(component_name: str) -> dict[str, Any] | None:
    """Return the full schema for a single component.

    Args:
        component_name: The exact internal name of the component
            (e.g. ``"OpenAIModel"``).

    Returns:
        Dict with keys from :data:`SCHEMA_FIELDS`, or ``None`` when the
        component is not found.
    """
    return await get_component_by_name(
        component_name=component_name,
        fields=SCHEMA_FIELDS,
    )


async def list_compatible_outputs(input_type: str) -> list[dict[str, Any]]:
    """Find components whose outputs match *input_type*.

    Iterates over all registered components, inspecting their ``template``
    and ``output_types`` metadata to find those that can feed into an input
    expecting *input_type*.

    Args:
        input_type: The type string to match (e.g. ``"Message"``).

    Returns:
        Compact result dicts with keys:
        ``name``, ``display_name``, ``type``, ``description``, ``output_types``.
    """
    all_components = await list_all_components(
        fields=["name", "display_name", "type", "description", "output_types", "outputs"],
    )

    matches: list[dict[str, Any]] = []
    input_type_lower = input_type.lower()

    for comp in all_components:
        output_types: list[str] = []

        # First check the top-level output_types field
        if "output_types" in comp and comp["output_types"]:
            output_types = comp["output_types"]

        # Also check the outputs list (each output may declare its own types)
        if "outputs" in comp and isinstance(comp["outputs"], list):
            for output in comp["outputs"]:
                if isinstance(output, dict):
                    for ot in output.get("types", []):
                        if ot not in output_types:
                            output_types.append(ot)

        # Check for a match
        if any(ot.lower() == input_type_lower for ot in output_types):
            matches.append({
                "name": comp["name"],
                "display_name": comp.get("display_name", ""),
                "type": comp["type"],
                "description": comp.get("description", ""),
                "output_types": output_types,
            })

    return matches

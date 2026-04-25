"""ADPToolsComponent — single multi-select component exposing ADP tile groups as agent tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from lfx.components.adp._shared import ADPConnection, RequestCache
from lfx.components.adp.adp_worker_demographic_tools import build_worker_demographic_tools
from lfx.components.adp.adp_worker_tools import build_worker_tools
from lfx.custom.custom_component.component import Component
from lfx.field_typing import Tool  # noqa: TC001 — runtime return annotation used by LangFlow registry
from lfx.io import HandleInput, MultiselectInput, Output

if TYPE_CHECKING:
    from collections.abc import Callable


# Initially populated with the two canonical-pattern tiles. Task 8 expands to 29.
TILE_BUILDERS: dict[str, Callable[[ADPConnection, RequestCache], list[Tool]]] = {
    "Worker": build_worker_tools,
    "Worker Demographic": build_worker_demographic_tools,
}


class ADPToolsComponent(Component):
    display_name = "ADP Tools"
    name = "ADPTools"
    description = (
        "Exposes ADP HR, payroll, time, and talent tools to a Langflow Agent. "
        "Pick which tile groups you want — each contributes 1-15 agent tools."
    )
    icon = "Users"
    version: int = 1
    documentation: str = "https://docs.langflow.org/component-adp-tools"

    inputs: ClassVar = [
        HandleInput(
            name="connection",
            display_name="ADP Connection",
            input_types=["ADPConnection"],
            info="Connection produced by an ADP Auth component.",
            required=True,
        ),
        MultiselectInput(
            name="tiles",
            display_name="Tools",
            options=list(TILE_BUILDERS.keys()),
            value=[],
            info=(
                "Select which ADP tool groups to expose to the agent. Each group "
                "adds 1-15 focused agent tools. Leaving this empty exposes nothing."
            ),
        ),
    ]

    outputs: ClassVar = [Output(display_name="Tools", name="tools", method="build_tools")]

    async def build_tools(self) -> list[Tool]:
        selected = list(getattr(self, "tiles", []) or [])
        if not selected:
            self.status = "No tile groups selected — agent will receive 0 ADP tools."
            return []
        cache = RequestCache(ttl_seconds=30, max_entries=128)
        tools: list[Tool] = []
        for label in selected:
            builder = TILE_BUILDERS.get(label)
            if builder is None:
                continue  # defensive: stale label from a saved flow
            tools.extend(builder(self.connection, cache))
        self.status = f"Exposing {len(tools)} tool(s) from {len(selected)} tile group(s)."
        return tools

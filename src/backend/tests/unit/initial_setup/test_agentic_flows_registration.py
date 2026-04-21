"""Guardrail tests: shipped agentic flows are picked up by the loader at startup.

These tests don't mock the LLM provider or exercise the flow — they just assert
the JSON files exist in the expected directory and register with the loader.
"""

from __future__ import annotations

import pytest

from langflow.initial_setup.setup import load_agentic_flows


@pytest.mark.asyncio
async def test_data_mapper_auto_map_flow_is_loaded():
    flows = await load_agentic_flows()
    names = {flow_data.get("name") for _, flow_data in flows}
    assert "DataMapperAutoMap" in names, (
        f"DataMapperAutoMap flow missing from loaded flows; loaded: {names}"
    )


@pytest.mark.asyncio
async def test_data_mapper_auto_map_flow_has_required_shape():
    flows = await load_agentic_flows()
    matched = [
        flow_data for _, flow_data in flows if flow_data.get("name") == "DataMapperAutoMap"
    ]
    assert len(matched) == 1
    flow = matched[0]
    assert "data" in flow
    assert "data" in flow["data"]
    assert "nodes" in flow["data"]["data"]
    assert len(flow["data"]["data"]["nodes"]) > 0

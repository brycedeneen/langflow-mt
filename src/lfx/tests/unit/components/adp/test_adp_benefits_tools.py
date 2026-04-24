"""Tests for ADPBenefitsToolsComponent."""

from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.adp.adp_benefits_tools import (
    ADPBenefitsToolsComponent,
    PATH_BENEFICIARIES,
    PATH_DEPENDENTS,
    PATH_EXTERNAL_PLAN_CONFIRM,
    PATH_EXTERNAL_PLANS_PUBLISH,
)


def _make(connection, *, enable_mutations=False):
    return ADPBenefitsToolsComponent(connection=connection, enable_mutations=enable_mutations)


@pytest.mark.asyncio
async def test_read_tools_routing(adp_connection):
    c = _make(adp_connection)
    mock_call = AsyncMock(return_value={})
    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()

        await next(t for t in tools if t.name == "get_associate_beneficiaries").ainvoke({"associate_oid": "G3ABC"})
        assert mock_call.call_args.kwargs["path"] == PATH_BENEFICIARIES.format(aoid="G3ABC")

        await next(t for t in tools if t.name == "get_associate_dependents").ainvoke({"associate_oid": "G3ABC"})
        assert mock_call.call_args.kwargs["path"] == PATH_DEPENDENTS.format(aoid="G3ABC")


@pytest.mark.asyncio
async def test_write_tools_gated(adp_connection):
    c = _make(adp_connection, enable_mutations=False)
    tools = await c.build_tools()
    names = {t.name for t in tools}
    assert "publish_external_benefit_plans" not in names
    assert "confirm_external_benefit_plan_data" not in names

    c = _make(adp_connection, enable_mutations=True)
    tools = await c.build_tools()
    names = {t.name for t in tools}
    assert "publish_external_benefit_plans" in names
    assert "confirm_external_benefit_plan_data" in names


@pytest.mark.asyncio
async def test_publish_and_confirm_routes(adp_connection):
    c = _make(adp_connection, enable_mutations=True)
    mock_call = AsyncMock(return_value={})
    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        await next(t for t in tools if t.name == "publish_external_benefit_plans").ainvoke({"body": {"x": 1}})
        assert mock_call.call_args.kwargs["path"] == PATH_EXTERNAL_PLANS_PUBLISH
        assert mock_call.call_args.kwargs["method"] == "POST"
        assert mock_call.call_args.kwargs["body"] == {"x": 1}

        await next(t for t in tools if t.name == "confirm_external_benefit_plan_data").ainvoke({"body": {"y": 2}})
        assert mock_call.call_args.kwargs["path"] == PATH_EXTERNAL_PLAN_CONFIRM

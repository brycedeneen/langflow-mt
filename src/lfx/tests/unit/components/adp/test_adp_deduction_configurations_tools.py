"""Tests for ADPDeductionConfigurationsToolsComponent."""

from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.adp.adp_deduction_configurations_tools import (
    ADPDeductionConfigurationsToolsComponent,
    PATH,
)


@pytest.mark.asyncio
async def test_call_no_params(adp_connection):
    c = ADPDeductionConfigurationsToolsComponent(connection=adp_connection)
    mock_call = AsyncMock(return_value={})
    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        await tools[0].ainvoke({})
    assert mock_call.call_args.kwargs["path"] == PATH
    assert mock_call.call_args.kwargs["params"] is None


@pytest.mark.asyncio
async def test_call_with_paging(adp_connection):
    c = ADPDeductionConfigurationsToolsComponent(connection=adp_connection)
    mock_call = AsyncMock(return_value={})
    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        await tools[0].ainvoke({"$filter": "statusCode eq 'A'", "$top": 10})
    assert mock_call.call_args.kwargs["params"] == {"$filter": "statusCode eq 'A'", "$top": 10}


def test_path_constant():
    assert PATH == "/payroll/v3/deduction-configurations"

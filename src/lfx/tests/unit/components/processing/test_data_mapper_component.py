import json
from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.processing.data_mapper import DataMapperComponent
from lfx.schema import Data, DataFrame, Message
from lfx.schema.data import JSON


def _valid_config():
    return {
        "driver_index": 0,
        "inputs": [
            {
                "alias": "workers",
                "schema_source": "autodetect",
                "schema": {"fields": [{"name": "user_id", "type": "str", "required": True}]},
            }
        ],
        "destination_schema": [
            {"name": "External_ID", "type": "str", "required": True, "default": None},
        ],
        "mappings": [
            {
                "destination": "External_ID",
                "transform": "direct",
                "sources": [{"input": "workers", "field": "user_id"}],
            }
        ],
    }


def test_component_declares_expected_inputs():
    input_names = [i.name for i in DataMapperComponent.inputs]
    assert input_names == ["inputs", "mapping_config", "output_type"]


def test_component_declares_four_outputs():
    output_types = [o.types[0] for o in DataMapperComponent.outputs]
    assert set(output_types) == {"Data", "DataFrame", "Message", "JSON"}


@pytest.mark.asyncio
async def test_component_build_data_output():
    cmp = DataMapperComponent()
    cmp.inputs = [{"user_id": "u-1"}]
    cmp.mapping_config = json.dumps(_valid_config())
    cmp.output_type = "Data"
    result = await cmp.build_data()
    assert isinstance(result, Data)
    assert result.data["External_ID"] == "u-1"


@pytest.mark.asyncio
async def test_component_build_dataframe_output():
    cmp = DataMapperComponent()
    cmp.inputs = [[{"user_id": "u-1"}, {"user_id": "u-2"}]]
    cmp.mapping_config = json.dumps(_valid_config())
    cmp.output_type = "DataFrame"
    result = await cmp.build_dataframe()
    assert isinstance(result, DataFrame)


@pytest.mark.asyncio
async def test_component_build_message_output():
    cmp = DataMapperComponent()
    cmp.inputs = [{"user_id": "u-1"}]
    cmp.mapping_config = json.dumps(_valid_config())
    cmp.output_type = "Message"
    result = await cmp.build_message()
    assert isinstance(result, Message)


@pytest.mark.asyncio
async def test_component_build_json_output():
    cmp = DataMapperComponent()
    cmp.inputs = [[{"user_id": "u-1"}]]
    cmp.mapping_config = json.dumps(_valid_config())
    cmp.output_type = "JSON"
    result = await cmp.build_json()
    assert isinstance(result, JSON)


@pytest.mark.asyncio
async def test_component_rejects_invalid_mapping_config_json():
    cmp = DataMapperComponent()
    cmp.inputs = [{"user_id": "u-1"}]
    cmp.mapping_config = "not-valid-json"
    cmp.output_type = "Data"
    with pytest.raises(ValueError, match="mapping_config"):
        await cmp.build_data()


@pytest.mark.asyncio
async def test_component_rejects_config_schema_violation():
    bad_cfg = _valid_config()
    bad_cfg["driver_index"] = 99
    cmp = DataMapperComponent()
    cmp.inputs = [{"user_id": "u-1"}]
    cmp.mapping_config = json.dumps(bad_cfg)
    cmp.output_type = "Data"
    with pytest.raises(ValueError, match="mapping_config"):
        await cmp.build_data()


@pytest.mark.asyncio
async def test_component_resolves_variable_via_env(monkeypatch):
    monkeypatch.setenv("MAPPER_TEST_VAR", "hello-from-env")
    cfg = _valid_config()
    cfg["destination_schema"].append(
        {"name": "Greeting", "type": "str", "required": False, "default": ""}
    )
    cfg["mappings"].append(
        {
            "destination": "Greeting",
            "transform": "variable",
            "sources": [],
            "config": {"variable": "MAPPER_TEST_VAR"},
        }
    )

    cmp = DataMapperComponent()
    cmp.inputs = [{"user_id": "u-1"}]
    cmp.mapping_config = json.dumps(cfg)
    cmp.output_type = "Data"
    result = await cmp.build_data()
    assert result.data["Greeting"] == "hello-from-env"


@pytest.mark.asyncio
async def test_component_resolves_variable_via_service_when_env_absent():
    cfg = _valid_config()
    cfg["destination_schema"].append(
        {"name": "ApiKey", "type": "str", "required": False, "default": ""}
    )
    cfg["mappings"].append(
        {
            "destination": "ApiKey",
            "transform": "variable",
            "sources": [],
            "config": {"variable": "customer_api_key"},
        }
    )

    cmp = DataMapperComponent()
    cmp.inputs = [{"user_id": "u-1"}]
    cmp.mapping_config = json.dumps(cfg)
    cmp.output_type = "Data"
    cmp._user_id = "00000000-0000-0000-0000-000000000001"

    # Patch the VariableService entrypoint used by the component.
    mock_service = AsyncMock()
    mock_service.get_variable.return_value = "sk-123"
    with patch(
        "lfx.components.processing.data_mapper.get_variable_service",
        return_value=mock_service,
    ), patch(
        "lfx.components.processing.data_mapper.session_scope"
    ) as scope_cm:
        # async context manager returning a dummy session
        scope_cm.return_value.__aenter__ = AsyncMock(return_value=object())
        scope_cm.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await cmp.build_data()

    assert result.data["ApiKey"] == "sk-123"
    mock_service.get_variable.assert_awaited_once()


@pytest.mark.asyncio
async def test_component_unknown_variable_becomes_blank():
    cfg = _valid_config()
    cfg["destination_schema"].append(
        {"name": "Maybe", "type": "str", "required": False, "default": ""}
    )
    cfg["mappings"].append(
        {
            "destination": "Maybe",
            "transform": "variable",
            "sources": [],
            "config": {"variable": "definitely_unknown"},
        }
    )

    cmp = DataMapperComponent()
    cmp.inputs = [{"user_id": "u-1"}]
    cmp.mapping_config = json.dumps(cfg)
    cmp.output_type = "Data"
    cmp._user_id = None  # no user → skip service call, env already absent

    result = await cmp.build_data()
    assert result.data["Maybe"] == ""


def test_update_outputs_auto_keeps_all_four():
    cmp = DataMapperComponent()
    frontend_node = {"outputs": []}
    cmp.update_outputs(frontend_node, "output_type", "Auto")
    names = [o["name"] for o in frontend_node["outputs"]]
    assert set(names) == {"data_output", "dataframe_output", "message_output", "json_output"}


def test_update_outputs_explicit_data_filters_to_one():
    cmp = DataMapperComponent()
    frontend_node = {"outputs": []}
    cmp.update_outputs(frontend_node, "output_type", "Data")
    assert [o["name"] for o in frontend_node["outputs"]] == ["data_output"]


def test_update_outputs_explicit_dataframe_filters_to_one():
    cmp = DataMapperComponent()
    frontend_node = {"outputs": []}
    cmp.update_outputs(frontend_node, "output_type", "DataFrame")
    assert [o["name"] for o in frontend_node["outputs"]] == ["dataframe_output"]


def test_update_outputs_explicit_message_filters_to_one():
    cmp = DataMapperComponent()
    frontend_node = {"outputs": []}
    cmp.update_outputs(frontend_node, "output_type", "Message")
    assert [o["name"] for o in frontend_node["outputs"]] == ["message_output"]


def test_update_outputs_explicit_json_filters_to_one():
    cmp = DataMapperComponent()
    frontend_node = {"outputs": []}
    cmp.update_outputs(frontend_node, "output_type", "JSON")
    assert [o["name"] for o in frontend_node["outputs"]] == ["json_output"]


def test_update_outputs_ignores_other_fields():
    cmp = DataMapperComponent()
    frontend_node = {"outputs": [{"name": "existing"}]}
    cmp.update_outputs(frontend_node, "mapping_config", "anything")
    # Should be untouched
    assert frontend_node["outputs"] == [{"name": "existing"}]


def test_component_is_discoverable_from_bundle():
    from lfx.components import processing
    cls = getattr(processing, "DataMapperComponent", None)
    assert cls is not None
    assert cls.__name__ == "DataMapperComponent"
    assert "DataMapperComponent" in processing.__all__

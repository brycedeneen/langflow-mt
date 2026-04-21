import pytest
from pydantic import ValidationError

from lfx.components.processing._data_mapper.config_schema import MapperConfig


def _minimal_valid_config():
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


def test_valid_minimal_config_parses():
    cfg = MapperConfig.model_validate(_minimal_valid_config())
    assert cfg.driver_index == 0
    assert cfg.inputs[0].alias == "workers"


def test_driver_index_out_of_range_fails():
    cfg = _minimal_valid_config()
    cfg["driver_index"] = 5
    with pytest.raises(ValidationError, match="driver_index"):
        MapperConfig.model_validate(cfg)


def test_duplicate_input_aliases_fail():
    cfg = _minimal_valid_config()
    cfg["inputs"].append(
        {
            "alias": "workers",  # duplicate
            "schema_source": "autodetect",
            "schema": {"fields": []},
            "join": {"on": [{"driver_field": "x", "lookup_field": "y"}]},
        }
    )
    with pytest.raises(ValidationError, match="duplicate"):
        MapperConfig.model_validate(cfg)


def test_non_driver_input_must_have_join():
    cfg = _minimal_valid_config()
    cfg["inputs"].append(
        {
            "alias": "jobs",
            "schema_source": "autodetect",
            "schema": {"fields": []},
            # no join — should fail
        }
    )
    with pytest.raises(ValidationError, match="join"):
        MapperConfig.model_validate(cfg)


def test_driver_input_must_not_have_join():
    cfg = _minimal_valid_config()
    cfg["inputs"][0]["join"] = {"on": [{"driver_field": "x", "lookup_field": "y"}]}
    with pytest.raises(ValidationError, match="driver"):
        MapperConfig.model_validate(cfg)


def test_mapping_references_unknown_destination_fails():
    cfg = _minimal_valid_config()
    cfg["mappings"][0]["destination"] = "nonexistent_field"
    with pytest.raises(ValidationError, match="destination"):
        MapperConfig.model_validate(cfg)


def test_mapping_references_unknown_input_alias_fails():
    cfg = _minimal_valid_config()
    cfg["mappings"][0]["sources"][0]["input"] = "not_an_input"
    with pytest.raises(ValidationError, match="input"):
        MapperConfig.model_validate(cfg)


def test_required_destination_with_no_mapping_fails():
    cfg = _minimal_valid_config()
    cfg["destination_schema"].append(
        {"name": "Email", "type": "str", "required": True, "default": None}
    )
    # Email has no mapping entry — required fields must be mapped at config time.
    with pytest.raises(ValidationError, match="Email"):
        MapperConfig.model_validate(cfg)


def test_schema_source_enum_is_enforced():
    cfg = _minimal_valid_config()
    cfg["inputs"][0]["schema_source"] = "xml"
    with pytest.raises(ValidationError):
        MapperConfig.model_validate(cfg)


def test_transform_type_enum_is_enforced():
    cfg = _minimal_valid_config()
    cfg["mappings"][0]["transform"] = "not_a_transform"
    with pytest.raises(ValidationError):
        MapperConfig.model_validate(cfg)

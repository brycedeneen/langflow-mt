import pytest

from lfx.components.processing._data_mapper.config_schema import MapperConfig
from lfx.components.processing._data_mapper.engine import package_output, run
from lfx.schema import Data, DataFrame, Message
from lfx.schema.data import JSON


def _cfg(destination_schema, mappings, *, has_jobs=False):
    inputs = [
        {
            "alias": "workers",
            "schema_source": "autodetect",
            "schema": {"fields": [{"name": "user_id", "type": "str", "required": True}]},
        }
    ]
    if has_jobs:
        inputs.append(
            {
                "alias": "jobs",
                "schema_source": "autodetect",
                "schema": {"fields": []},
                "join": {"on": [{"driver_field": "job_id", "lookup_field": "id"}]},
            }
        )
    return MapperConfig.model_validate(
        {
            "driver_index": 0,
            "inputs": inputs,
            "destination_schema": destination_schema,
            "mappings": mappings,
        }
    )


def test_run_single_driver_row_direct_mapping():
    cfg = _cfg(
        destination_schema=[{"name": "External_ID", "type": "str", "required": True}],
        mappings=[
            {
                "destination": "External_ID",
                "transform": "direct",
                "sources": [{"input": "workers", "field": "user_id"}],
            }
        ],
    )
    out = run(cfg, inputs=[[{"user_id": "u-1"}]], variable_resolver=lambda n: None)
    assert out == [{"External_ID": "u-1"}]


def test_run_list_driver_emits_one_output_per_row():
    cfg = _cfg(
        destination_schema=[{"name": "External_ID", "type": "str", "required": False}],
        mappings=[
            {
                "destination": "External_ID",
                "transform": "direct",
                "sources": [{"input": "workers", "field": "user_id"}],
            }
        ],
    )
    out = run(
        cfg,
        inputs=[[{"user_id": "u-1"}, {"user_id": "u-2"}, {"user_id": "u-3"}]],
        variable_resolver=lambda n: None,
    )
    assert out == [{"External_ID": "u-1"}, {"External_ID": "u-2"}, {"External_ID": "u-3"}]


def test_run_optional_missing_uses_type_blank_default():
    cfg = _cfg(
        destination_schema=[
            {"name": "External_ID", "type": "str", "required": True},
            {"name": "Name", "type": "str", "required": False, "default": ""},
            {"name": "Tags", "type": "list", "required": False, "default": []},
            {"name": "Score", "type": "float", "required": False, "default": None},
        ],
        mappings=[
            {
                "destination": "External_ID",
                "transform": "direct",
                "sources": [{"input": "workers", "field": "user_id"}],
            },
            {
                "destination": "Name",
                "transform": "direct",
                "sources": [{"input": "workers", "field": "name"}],
            },
            {
                "destination": "Tags",
                "transform": "direct",
                "sources": [{"input": "workers", "field": "tags"}],
            },
            {
                "destination": "Score",
                "transform": "direct",
                "sources": [{"input": "workers", "field": "score"}],
            },
        ],
    )
    out = run(cfg, inputs=[[{"user_id": "u-1"}]], variable_resolver=lambda n: None)
    assert out == [{"External_ID": "u-1", "Name": "", "Tags": [], "Score": None}]


def test_run_required_missing_logs_error_and_emits_default():
    cfg = _cfg(
        destination_schema=[
            {"name": "External_ID", "type": "str", "required": True, "default": "UNKNOWN"}
        ],
        mappings=[
            {
                "destination": "External_ID",
                "transform": "direct",
                "sources": [{"input": "workers", "field": "missing_field"}],
            }
        ],
    )
    out = run(cfg, inputs=[[{"user_id": "u-1"}]], variable_resolver=lambda n: None)
    # Row is still emitted; default substitutes; error count tracked on engine (see test_errors)
    assert out == [{"External_ID": "UNKNOWN"}]


def test_run_left_join_lookup_populates_via_template():
    cfg = _cfg(
        destination_schema=[
            {"name": "User", "type": "str", "required": True},
            {"name": "Title", "type": "str", "required": False},
        ],
        mappings=[
            {
                "destination": "User",
                "transform": "direct",
                "sources": [{"input": "workers", "field": "user_id"}],
            },
            {
                "destination": "Title",
                "transform": "template",
                "sources": [],
                "config": {"template": "{{ jobs.title }}"},
            },
        ],
        has_jobs=True,
    )
    out = run(
        cfg,
        inputs=[
            [{"user_id": "u-1", "job_id": "j-1"}, {"user_id": "u-2", "job_id": "j-99"}],
            [{"id": "j-1", "title": "Engineer"}],
        ],
        variable_resolver=lambda n: None,
    )
    assert out == [
        {"User": "u-1", "Title": "Engineer"},
        {"User": "u-2", "Title": ""},  # unmatched lookup → Jinja renders undefined as ""
    ]


def test_run_type_coercion_str_to_int():
    cfg = _cfg(
        destination_schema=[{"name": "Count", "type": "int", "required": False}],
        mappings=[
            {
                "destination": "Count",
                "transform": "direct",
                "sources": [{"input": "workers", "field": "count"}],
            }
        ],
    )
    out = run(cfg, inputs=[[{"count": "42"}]], variable_resolver=lambda n: None)
    assert out == [{"Count": 42}]


def test_run_type_coercion_failure_leaves_raw_value_and_warns():
    cfg = _cfg(
        destination_schema=[{"name": "Count", "type": "int", "required": False}],
        mappings=[
            {
                "destination": "Count",
                "transform": "direct",
                "sources": [{"input": "workers", "field": "count"}],
            }
        ],
    )
    out = run(cfg, inputs=[[{"count": "not-a-number"}]], variable_resolver=lambda n: None)
    # Coercion best-effort: leaves raw value, emits a warning log — row still produced.
    assert out == [{"Count": "not-a-number"}]


def test_run_single_record_input_treated_as_one_row_list():
    cfg = _cfg(
        destination_schema=[{"name": "External_ID", "type": "str", "required": True}],
        mappings=[
            {
                "destination": "External_ID",
                "transform": "direct",
                "sources": [{"input": "workers", "field": "user_id"}],
            }
        ],
    )
    # Pass a single dict (not wrapped in a list) — engine normalizes.
    out = run(cfg, inputs=[{"user_id": "u-1"}], variable_resolver=lambda n: None)
    assert out == [{"External_ID": "u-1"}]


def test_run_expression_can_access_lookup_field_via_dot_notation():
    cfg = _cfg(
        destination_schema=[
            {"name": "User", "type": "str", "required": True},
            {"name": "AdjustedSalary", "type": "float", "required": False},
        ],
        mappings=[
            {
                "destination": "User",
                "transform": "direct",
                "sources": [{"input": "workers", "field": "user_id"}],
            },
            {
                "destination": "AdjustedSalary",
                "transform": "expression",
                "sources": [],
                "config": {"expression": "jobs.salary * 1.1"},
            },
        ],
        has_jobs=True,
    )
    out = run(
        cfg,
        inputs=[
            [{"user_id": "u-1", "job_id": "j-1"}],
            [{"id": "j-1", "salary": 100}],
        ],
        variable_resolver=lambda n: None,
    )
    assert out[0]["User"] == "u-1"
    assert out[0]["AdjustedSalary"] == pytest.approx(110.0)


def test_run_direct_mapping_works_against_simplenamespace_lookup():
    cfg = _cfg(
        destination_schema=[
            {"name": "User", "type": "str", "required": True},
            {"name": "JobTitle", "type": "str", "required": False},
        ],
        mappings=[
            {
                "destination": "User",
                "transform": "direct",
                "sources": [{"input": "workers", "field": "user_id"}],
            },
            {
                "destination": "JobTitle",
                "transform": "direct",
                "sources": [{"input": "jobs", "field": "title"}],
            },
        ],
        has_jobs=True,
    )
    out = run(
        cfg,
        inputs=[
            [{"user_id": "u-1", "job_id": "j-1"}],
            [{"id": "j-1", "title": "Engineer"}],
        ],
        variable_resolver=lambda n: None,
    )
    assert out[0]["JobTitle"] == "Engineer"


def test_package_output_auto_list_returns_dataframe():
    rows = [{"a": 1}, {"a": 2}]
    result = package_output(rows, output_type="Auto", driver_was_list=True)
    assert isinstance(result, DataFrame)


def test_package_output_auto_single_record_returns_data():
    rows = [{"a": 1}]
    result = package_output(rows, output_type="Auto", driver_was_list=False)
    assert isinstance(result, Data)
    assert result.data["a"] == 1


def test_package_output_explicit_dataframe():
    rows = [{"a": 1}]
    result = package_output(rows, output_type="DataFrame", driver_was_list=False)
    assert isinstance(result, DataFrame)


def test_package_output_explicit_data_single_row():
    rows = [{"a": 1}]
    result = package_output(rows, output_type="Data", driver_was_list=True)
    assert isinstance(result, Data)


def test_package_output_explicit_data_multi_row_wraps_records():
    rows = [{"a": 1}, {"a": 2}]
    # Convention: Data output for multi-row wraps under "records" key.
    result = package_output(rows, output_type="Data", driver_was_list=True)
    assert isinstance(result, Data)
    assert result.data == {"records": [{"a": 1}, {"a": 2}]}


def test_package_output_explicit_json():
    rows = [{"a": 1}, {"a": 2}]
    result = package_output(rows, output_type="JSON", driver_was_list=True)
    assert isinstance(result, JSON)


def test_package_output_explicit_message_serializes_to_json_text():
    import json as _json
    rows = [{"a": 1}, {"a": 2}]
    result = package_output(rows, output_type="Message", driver_was_list=True)
    assert isinstance(result, Message)
    assert _json.loads(result.text) == rows


def test_package_output_empty_rows_auto_list():
    result = package_output([], output_type="Auto", driver_was_list=True)
    assert isinstance(result, DataFrame)


def test_package_output_empty_rows_auto_single():
    result = package_output([], output_type="Auto", driver_was_list=False)
    assert isinstance(result, Data)
    assert result.data == {}

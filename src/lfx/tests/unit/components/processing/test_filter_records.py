from lfx.components.processing.filter_records import FilterRecordsComponent


def test_component_metadata():
    assert FilterRecordsComponent.display_name == "Filter Records"
    assert FilterRecordsComponent.name == "FilterRecords"
    assert FilterRecordsComponent.icon == "filter"
    assert FilterRecordsComponent.version == 1
    assert len(FilterRecordsComponent.changelog) == 1
    assert FilterRecordsComponent.changelog[0].version == 1


def test_component_declares_expected_inputs():
    input_names = [i.name for i in FilterRecordsComponent.inputs]
    assert input_names == ["records", "conditions", "combinator", "mode"]


def test_component_declares_two_outputs():
    output_names = [o.name for o in FilterRecordsComponent.outputs]
    assert output_names == ["matched", "unmatched"]


def test_component_keywords_include_filter():
    assert "filter" in FilterRecordsComponent.metadata["keywords"]


import pandas as pd
import pytest

from lfx.schema import Data, DataFrame


def _records():
    return [
        Data(data={"name": "Alice", "age": 30, "country": "US"}),
        Data(data={"name": "Bob", "age": 25, "country": "UK"}),
        Data(data={"name": "Charlie", "age": 35, "country": "US"}),
    ]


def _df():
    return DataFrame(pd.DataFrame([
        {"name": "Alice", "age": 30, "country": "US"},
        {"name": "Bob", "age": 25, "country": "UK"},
        {"name": "Charlie", "age": 35, "country": "US"},
    ]))


def _new(records, conditions, combinator="AND", mode="Keep matching"):
    cmp = FilterRecordsComponent()
    cmp.records = records if isinstance(records, list) else [records]
    cmp.conditions = conditions
    cmp.combinator = combinator
    cmp.mode = mode
    return cmp


@pytest.mark.asyncio
async def test_filter_data_list_single_condition_keep():
    cmp = _new(_records(), [{"field": "country", "operator": "equals", "value": "US"}])
    matched = await cmp.build_matched()
    assert isinstance(matched, list)
    assert [d.data["name"] for d in matched] == ["Alice", "Charlie"]


@pytest.mark.asyncio
async def test_filter_data_list_single_condition_unmatched_complements():
    cmp = _new(_records(), [{"field": "country", "operator": "equals", "value": "US"}])
    unmatched = await cmp.build_unmatched()
    assert [d.data["name"] for d in unmatched] == ["Bob"]


@pytest.mark.asyncio
async def test_filter_data_list_and_combinator():
    cmp = _new(
        _records(),
        [
            {"field": "country", "operator": "equals", "value": "US"},
            {"field": "age", "operator": "greater than", "value": "31"},
        ],
        combinator="AND",
    )
    matched = await cmp.build_matched()
    assert [d.data["name"] for d in matched] == ["Charlie"]


@pytest.mark.asyncio
async def test_filter_data_list_or_combinator():
    cmp = _new(
        _records(),
        [
            {"field": "country", "operator": "equals", "value": "UK"},
            {"field": "age", "operator": "greater than", "value": "31"},
        ],
        combinator="OR",
    )
    matched = await cmp.build_matched()
    assert [d.data["name"] for d in matched] == ["Bob", "Charlie"]


@pytest.mark.asyncio
async def test_filter_data_list_exclude_mode_inverts():
    cmp = _new(
        _records(),
        [{"field": "country", "operator": "equals", "value": "US"}],
        mode="Exclude matching",
    )
    matched = await cmp.build_matched()
    unmatched = await cmp.build_unmatched()
    # In Exclude mode, US records should land in 'unmatched'
    assert [d.data["name"] for d in matched] == ["Bob"]
    assert [d.data["name"] for d in unmatched] == ["Alice", "Charlie"]


@pytest.mark.asyncio
async def test_filter_dataframe_single_condition():
    cmp = _new(_df(), [{"field": "country", "operator": "equals", "value": "US"}])
    matched = await cmp.build_matched()
    assert isinstance(matched, DataFrame)
    assert matched.to_dict(orient="records") == [
        {"name": "Alice", "age": 30, "country": "US"},
        {"name": "Charlie", "age": 35, "country": "US"},
    ]


@pytest.mark.asyncio
async def test_filter_dataframe_or_combinator():
    cmp = _new(
        _df(),
        [
            {"field": "country", "operator": "equals", "value": "UK"},
            {"field": "age", "operator": "less than", "value": "31"},
        ],
        combinator="OR",
    )
    matched = await cmp.build_matched()
    assert sorted(d["name"] for d in matched.to_dict(orient="records")) == ["Alice", "Bob"]


@pytest.mark.asyncio
async def test_filter_single_data_returns_list_of_one():
    """is_list=True wraps single Data → list[Data] of one record out.

    Output shape rule: list[Data] unless ALL inputs are DataFrames.
    """
    cmp = _new(
        Data(data={"name": "Alice", "country": "US"}),
        [{"field": "country", "operator": "equals", "value": "US"}],
    )
    matched = await cmp.build_matched()
    assert isinstance(matched, list)
    assert len(matched) == 1
    assert matched[0].data == {"name": "Alice", "country": "US"}


@pytest.mark.asyncio
async def test_filter_missing_field_treated_as_not_matching():
    records = [
        Data(data={"name": "Alice", "country": "US"}),
        Data(data={"name": "Bob"}),  # no 'country' key
    ]
    cmp = _new(records, [{"field": "country", "operator": "equals", "value": "US"}])
    matched = await cmp.build_matched()
    assert [d.data["name"] for d in matched] == ["Alice"]


@pytest.mark.asyncio
async def test_filter_empty_input_empty_output():
    cmp = _new([], [{"field": "country", "operator": "equals", "value": "US"}])
    matched = await cmp.build_matched()
    unmatched = await cmp.build_unmatched()
    assert matched == []
    assert unmatched == []


@pytest.mark.asyncio
async def test_filter_is_list_handle_input_framework_shape():
    """is_list=True means the framework delivers self.records as a list.
    Verify the component handles the framework's wrapping correctly.
    """
    cmp = FilterRecordsComponent()
    # When the user wires a single Data, framework delivers [Data(...)].
    cmp.records = [Data(data={"name": "Alice", "country": "US"})]
    cmp.conditions = [{"field": "country", "operator": "equals", "value": "US"}]
    cmp.combinator = "AND"
    cmp.mode = "Keep matching"
    matched = await cmp.build_matched()
    # Output rule: list[Data] unless all inputs are DataFrames.
    assert isinstance(matched, list)
    assert len(matched) == 1
    assert matched[0].data == {"name": "Alice", "country": "US"}


@pytest.mark.asyncio
async def test_validation_invalid_regex_raises():
    cmp = _new(
        _records(),
        [{"field": "name", "operator": "matches regex", "value": "[unclosed"}],
    )
    with pytest.raises(ValueError, match="Invalid regex"):
        await cmp.build_matched()


@pytest.mark.asyncio
async def test_validation_between_wrong_value_count_raises():
    cmp = _new(
        _records(),
        [{"field": "age", "operator": "between", "value": "10"}],
    )
    with pytest.raises(ValueError, match="between"):
        await cmp.build_matched()


@pytest.mark.asyncio
async def test_validation_empty_conditions_with_keep_mode_raises():
    cmp = _new(_records(), [], mode="Keep matching")
    with pytest.raises(ValueError, match="at least one condition"):
        await cmp.build_matched()


@pytest.mark.asyncio
async def test_validation_empty_conditions_with_exclude_mode_returns_all_unmatched():
    cmp = _new(_records(), [], mode="Exclude matching")
    matched = await cmp.build_matched()
    unmatched = await cmp.build_unmatched()
    # Empty conditions are vacuously True; Exclude inverts to False;
    # so all records land in unmatched.
    assert [d.data["name"] for d in matched] == []
    assert [d.data["name"] for d in unmatched] == ["Alice", "Bob", "Charlie"]


@pytest.mark.asyncio
async def test_validation_skips_blank_rows():
    """User adds a row, doesn't fill it in. Should be ignored, not raise."""
    cmp = _new(
        _records(),
        [
            {"field": "country", "operator": "equals", "value": "US"},
            {"field": "", "operator": "equals", "value": ""},
        ],
    )
    matched = await cmp.build_matched()
    assert [d.data["name"] for d in matched] == ["Alice", "Charlie"]


def test_component_is_registered_in_bundle():
    from lfx.components import processing

    assert "FilterRecordsComponent" in processing.__all__
    assert processing.FilterRecordsComponent is FilterRecordsComponent

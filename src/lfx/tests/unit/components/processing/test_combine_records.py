import pytest

from lfx.components.processing.combine_records import CombineRecordsComponent


def test_component_metadata():
    assert CombineRecordsComponent.display_name == "Combine Records"
    assert CombineRecordsComponent.name == "CombineRecords"
    assert CombineRecordsComponent.icon == "merge"
    assert CombineRecordsComponent.version == 1
    assert len(CombineRecordsComponent.changelog) == 1


def test_component_declares_expected_inputs():
    input_names = [i.name for i in CombineRecordsComponent.inputs]
    assert input_names == ["mode", "left", "right", "dedupe_keys", "join_keys", "join_type"]


def test_component_declares_one_output():
    output_names = [o.name for o in CombineRecordsComponent.outputs]
    assert output_names == ["combined"]


def test_dynamic_fields_hidden_in_append_mode():
    cmp = CombineRecordsComponent()
    build_config = {
        "dedupe_keys": {"show": True},
        "join_keys": {"show": True},
        "join_type": {"show": True},
    }
    result = cmp.update_build_config(build_config, "Append", "mode")
    assert result["dedupe_keys"]["show"] is False
    assert result["join_keys"]["show"] is False
    assert result["join_type"]["show"] is False


def test_dynamic_fields_dedupe_visible_in_union_mode():
    cmp = CombineRecordsComponent()
    build_config = {
        "dedupe_keys": {"show": False},
        "join_keys": {"show": True},
        "join_type": {"show": True},
    }
    result = cmp.update_build_config(build_config, "Union (dedupe)", "mode")
    assert result["dedupe_keys"]["show"] is True
    assert result["join_keys"]["show"] is False
    assert result["join_type"]["show"] is False


def test_dynamic_fields_join_visible_in_merge_mode():
    cmp = CombineRecordsComponent()
    build_config = {
        "dedupe_keys": {"show": True},
        "join_keys": {"show": False},
        "join_type": {"show": False},
    }
    result = cmp.update_build_config(build_config, "Merge by key", "mode")
    assert result["dedupe_keys"]["show"] is False
    assert result["join_keys"]["show"] is True
    assert result["join_type"]["show"] is True


import pandas as pd

from lfx.schema import Data, DataFrame


def _data_list(records):
    return [Data(data=r) for r in records]


def _df(records):
    return DataFrame(pd.DataFrame(records))


def _new_combine(left, right, mode="Append", dedupe_keys="", join_keys="", join_type="inner"):
    cmp = CombineRecordsComponent()
    cmp.left = left
    cmp.right = right
    cmp.mode = mode
    cmp.dedupe_keys = dedupe_keys
    cmp.join_keys = join_keys
    cmp.join_type = join_type
    return cmp


@pytest.mark.asyncio
async def test_append_data_lists_preserves_order():
    left = _data_list([{"id": 1}, {"id": 2}])
    right = _data_list([{"id": 3}, {"id": 4}])
    cmp = _new_combine(left, right, mode="Append")
    result = await cmp.build_combined()
    assert isinstance(result, list)
    assert [d.data["id"] for d in result] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_append_dataframes_preserves_order():
    left = _df([{"id": 1}, {"id": 2}])
    right = _df([{"id": 3}, {"id": 4}])
    cmp = _new_combine(left, right, mode="Append")
    result = await cmp.build_combined()
    assert isinstance(result, DataFrame)
    assert [r["id"] for r in result.to_dict(orient="records")] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_append_does_not_dedupe():
    left = _data_list([{"id": 1}, {"id": 2}])
    right = _data_list([{"id": 1}, {"id": 3}])
    cmp = _new_combine(left, right, mode="Append")
    result = await cmp.build_combined()
    assert [d.data["id"] for d in result] == [1, 2, 1, 3]


@pytest.mark.asyncio
async def test_union_dedupe_by_full_equality():
    left = _data_list([{"id": 1, "name": "A"}, {"id": 2, "name": "B"}])
    right = _data_list([{"id": 1, "name": "A"}, {"id": 3, "name": "C"}])
    cmp = _new_combine(left, right, mode="Union (dedupe)", dedupe_keys="")
    result = await cmp.build_combined()
    assert [d.data["id"] for d in result] == [1, 2, 3]


@pytest.mark.asyncio
async def test_union_dedupe_by_single_key_first_occurrence_wins():
    """If two records share the dedupe key, the LEFT one survives."""
    left = _data_list([{"id": 1, "name": "Alice-L"}])
    right = _data_list([{"id": 1, "name": "Alice-R"}, {"id": 2, "name": "Bob"}])
    cmp = _new_combine(left, right, mode="Union (dedupe)", dedupe_keys="id")
    result = await cmp.build_combined()
    assert [(d.data["id"], d.data["name"]) for d in result] == [
        (1, "Alice-L"), (2, "Bob"),
    ]


@pytest.mark.asyncio
async def test_union_dedupe_by_multiple_keys():
    left = _data_list([
        {"a": 1, "b": "x", "v": "L1"},
        {"a": 1, "b": "y", "v": "L2"},
    ])
    right = _data_list([
        {"a": 1, "b": "x", "v": "R1"},  # dup of left[0] by (a, b)
        {"a": 2, "b": "x", "v": "R2"},
    ])
    cmp = _new_combine(left, right, mode="Union (dedupe)", dedupe_keys="a, b")
    result = await cmp.build_combined()
    assert [d.data["v"] for d in result] == ["L1", "L2", "R2"]


@pytest.mark.asyncio
async def test_union_dedupe_dataframe():
    left = _df([{"id": 1, "name": "A"}, {"id": 2, "name": "B"}])
    right = _df([{"id": 1, "name": "A"}, {"id": 3, "name": "C"}])
    cmp = _new_combine(left, right, mode="Union (dedupe)", dedupe_keys="id")
    result = await cmp.build_combined()
    assert isinstance(result, DataFrame)
    assert [r["id"] for r in result.to_dict(orient="records")] == [1, 2, 3]


@pytest.mark.asyncio
async def test_empty_left_returns_right():
    left = _data_list([])
    right = _data_list([{"id": 1}])
    cmp = _new_combine(left, right, mode="Append")
    result = await cmp.build_combined()
    assert [d.data["id"] for d in result] == [1]


@pytest.mark.asyncio
async def test_empty_both_returns_empty():
    cmp = _new_combine(_data_list([]), _data_list([]), mode="Append")
    result = await cmp.build_combined()
    assert result == [] or (isinstance(result, list) and len(result) == 0)

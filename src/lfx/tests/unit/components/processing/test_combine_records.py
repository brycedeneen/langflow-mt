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


@pytest.mark.asyncio
async def test_merge_by_key_inner_join():
    left = _data_list([
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
        {"id": 3, "name": "Charlie"},
    ])
    right = _data_list([
        {"id": 1, "country": "US"},
        {"id": 2, "country": "UK"},
        {"id": 4, "country": "CA"},
    ])
    cmp = _new_combine(left, right, mode="Merge by key", join_keys="id", join_type="inner")
    result = await cmp.build_combined()
    rows = [d.data for d in result]
    assert sorted(r["id"] for r in rows) == [1, 2]
    by_id = {r["id"]: r for r in rows}
    assert by_id[1]["name"] == "Alice" and by_id[1]["country"] == "US"
    assert by_id[2]["name"] == "Bob" and by_id[2]["country"] == "UK"


@pytest.mark.asyncio
async def test_merge_by_key_left_join():
    left = _data_list([{"id": 1, "n": "A"}, {"id": 2, "n": "B"}])
    right = _data_list([{"id": 1, "c": "US"}])
    cmp = _new_combine(left, right, mode="Merge by key", join_keys="id", join_type="left")
    result = await cmp.build_combined()
    rows = sorted([d.data for d in result], key=lambda r: r["id"])
    assert rows[0]["id"] == 1 and rows[0]["c"] == "US"
    assert rows[1]["id"] == 2 and (rows[1].get("c") is None or pd.isna(rows[1]["c"]))


@pytest.mark.asyncio
async def test_merge_by_key_right_join():
    left = _data_list([{"id": 1, "n": "A"}])
    right = _data_list([{"id": 1, "c": "US"}, {"id": 2, "c": "UK"}])
    cmp = _new_combine(left, right, mode="Merge by key", join_keys="id", join_type="right")
    result = await cmp.build_combined()
    rows = sorted([d.data for d in result], key=lambda r: r["id"])
    assert len(rows) == 2
    assert rows[1]["id"] == 2


@pytest.mark.asyncio
async def test_merge_by_key_outer_join():
    left = _data_list([{"id": 1, "n": "A"}])
    right = _data_list([{"id": 2, "c": "UK"}])
    cmp = _new_combine(left, right, mode="Merge by key", join_keys="id", join_type="outer")
    result = await cmp.build_combined()
    assert len(result) == 2


@pytest.mark.asyncio
async def test_merge_by_key_multi_key():
    left = _data_list([
        {"a": 1, "b": "x", "n": "L1"},
        {"a": 1, "b": "y", "n": "L2"},
    ])
    right = _data_list([
        {"a": 1, "b": "x", "c": "R1"},
    ])
    cmp = _new_combine(left, right, mode="Merge by key", join_keys="a, b", join_type="inner")
    result = await cmp.build_combined()
    rows = [d.data for d in result]
    assert len(rows) == 1
    assert rows[0]["n"] == "L1" and rows[0]["c"] == "R1"


@pytest.mark.asyncio
async def test_merge_by_key_dataframe():
    left = _df([{"id": 1, "n": "A"}, {"id": 2, "n": "B"}])
    right = _df([{"id": 1, "c": "US"}, {"id": 2, "c": "UK"}])
    cmp = _new_combine(left, right, mode="Merge by key", join_keys="id", join_type="inner")
    result = await cmp.build_combined()
    assert isinstance(result, DataFrame)
    rows = sorted(result.to_dict(orient="records"), key=lambda r: r["id"])
    assert rows[0]["n"] == "A" and rows[0]["c"] == "US"


@pytest.mark.asyncio
async def test_merge_by_key_validation_missing_join_keys_raises():
    cmp = _new_combine(
        _data_list([{"id": 1}]),
        _data_list([{"id": 1}]),
        mode="Merge by key",
        join_keys="",
    )
    with pytest.raises(ValueError, match="join_keys"):
        await cmp.build_combined()


@pytest.mark.asyncio
async def test_merge_by_key_column_conflict_suffixes():
    """When both sides have a non-key column with the same name, pandas
    suffixes them with _left / _right (we use those suffixes explicitly)."""
    left = _data_list([{"id": 1, "name": "L"}])
    right = _data_list([{"id": 1, "name": "R"}])
    cmp = _new_combine(left, right, mode="Merge by key", join_keys="id", join_type="inner")
    result = await cmp.build_combined()
    row = result[0].data
    assert row["name_left"] == "L"
    assert row["name_right"] == "R"


@pytest.mark.asyncio
async def test_mixed_inputs_coerce_to_dataframe():
    """Data + DataFrame in → DataFrame out (per spec)."""
    left = _data_list([{"id": 1, "name": "A"}])
    right = _df([{"id": 2, "name": "B"}])
    cmp = _new_combine(left, right, mode="Append")
    result = await cmp.build_combined()
    assert isinstance(result, DataFrame)
    assert sorted(r["id"] for r in result.to_dict(orient="records")) == [1, 2]


@pytest.mark.asyncio
async def test_mixed_inputs_dataframe_left():
    left = _df([{"id": 1, "name": "A"}])
    right = _data_list([{"id": 2, "name": "B"}])
    cmp = _new_combine(left, right, mode="Append")
    result = await cmp.build_combined()
    assert isinstance(result, DataFrame)


def test_component_is_registered_in_bundle():
    from lfx.components import processing

    assert "CombineRecordsComponent" in processing.__all__
    assert processing.CombineRecordsComponent is CombineRecordsComponent

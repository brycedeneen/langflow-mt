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

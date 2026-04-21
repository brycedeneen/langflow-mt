import pytest

from lfx.components.processing._data_mapper.transforms import (
    _MISSING,
    dispatch,
)


def test_missing_sentinel_is_distinct_from_none():
    assert _MISSING is not None
    assert bool(_MISSING) is False  # convention: treat as falsy


def test_missing_sentinel_has_stable_repr():
    assert repr(_MISSING) == "_MISSING"


def test_dispatch_unknown_transform_type_raises():
    mapping = {"transform": "not_a_real_type", "sources": [], "config": {}}
    ctx = {}
    with pytest.raises(ValueError, match="unknown transform type"):
        dispatch(mapping, ctx, variable_resolver=lambda name: None)


def _direct(input_: str, field: str) -> dict:
    return {
        "transform": "direct",
        "sources": [{"input": input_, "field": field}],
        "config": {},
    }


def test_direct_transform_reads_driver_field():
    ctx = {"workers": {"user_id": "u-1", "email": "a@b.co"}}
    assert dispatch(_direct("workers", "user_id"), ctx, variable_resolver=lambda n: None) == "u-1"


def test_direct_transform_reads_lookup_field_through_alias():
    ctx = {
        "workers": {"user_id": "u-1"},
        "jobs": {"title": "Engineer", "id": "j-99"},
    }
    assert dispatch(_direct("jobs", "title"), ctx, variable_resolver=lambda n: None) == "Engineer"


def test_direct_transform_missing_input_alias_returns_missing():
    ctx = {"workers": {"user_id": "u-1"}}
    assert dispatch(_direct("jobs", "title"), ctx, variable_resolver=lambda n: None) is _MISSING


def test_direct_transform_lookup_is_none_when_unmatched():
    # Unmatched lookup input has ctx value `None` (not absent).
    ctx = {"workers": {"user_id": "u-1"}, "jobs": None}
    assert dispatch(_direct("jobs", "title"), ctx, variable_resolver=lambda n: None) is _MISSING


def test_direct_transform_missing_field_returns_missing():
    ctx = {"workers": {"user_id": "u-1"}}
    assert dispatch(_direct("workers", "nonexistent"), ctx, variable_resolver=lambda n: None) is _MISSING


def test_direct_transform_explicit_none_is_preserved():
    ctx = {"workers": {"user_id": None}}
    # Explicit None from source is preserved, NOT converted to _MISSING.
    assert dispatch(_direct("workers", "user_id"), ctx, variable_resolver=lambda n: None) is None


def _static(value):
    return {"transform": "static", "sources": [], "config": {"value": value}}


def test_static_returns_string_verbatim():
    assert dispatch(_static("EMEA"), {}, variable_resolver=lambda n: None) == "EMEA"


def test_static_returns_number_verbatim():
    assert dispatch(_static(42), {}, variable_resolver=lambda n: None) == 42


def test_static_returns_list_verbatim():
    assert dispatch(_static([1, 2, 3]), {}, variable_resolver=lambda n: None) == [1, 2, 3]


def test_static_returns_none_verbatim_not_missing():
    # `static` with value=None emits an explicit None, never _MISSING.
    assert dispatch(_static(None), {}, variable_resolver=lambda n: None) is None


def _variable(name):
    return {"transform": "variable", "sources": [], "config": {"variable": name}}


def test_variable_resolves_via_resolver():
    resolver = {"current_timestamp": "2026-04-21T10:00:00Z"}.get
    assert (
        dispatch(_variable("current_timestamp"), {}, variable_resolver=resolver)
        == "2026-04-21T10:00:00Z"
    )


def test_variable_unknown_name_returns_missing():
    resolver = {}.get
    assert dispatch(_variable("does_not_exist"), {}, variable_resolver=resolver) is _MISSING


def test_variable_requires_config_variable_name():
    mapping = {"transform": "variable", "sources": [], "config": {}}
    with pytest.raises(ValueError, match="config.variable"):
        dispatch(mapping, {}, variable_resolver=lambda n: None)

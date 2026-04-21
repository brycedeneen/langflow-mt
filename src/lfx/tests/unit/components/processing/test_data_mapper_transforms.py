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

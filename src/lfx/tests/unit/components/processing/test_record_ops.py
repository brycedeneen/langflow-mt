import pytest

from lfx.components.processing._record_ops import MISSING, get_path


@pytest.mark.parametrize(
    ("record", "path", "expected"),
    [
        ({"a": 1}, "a", 1),
        ({"a": {"b": 2}}, "a.b", 2),
        ({"a": {"b": {"c": 3}}}, "a.b.c", 3),
        ({"items": [{"sku": "x"}, {"sku": "y"}]}, "items[0].sku", "x"),
        ({"items": [{"sku": "x"}, {"sku": "y"}]}, "items[1].sku", "y"),
        ({"a": 1}, "missing", MISSING),
        ({"a": {"b": 2}}, "a.missing", MISSING),
        ({"items": []}, "items[0]", MISSING),
        ({"a": None}, "a.b", MISSING),
        ({}, "a", MISSING),
    ],
)
def test_get_path(record, path, expected):
    assert get_path(record, path) == expected

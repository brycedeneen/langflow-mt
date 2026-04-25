import pytest

from lfx.components.processing._record_ops import MISSING, get_path, OPERATORS, evaluate


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


@pytest.mark.parametrize(
    ("operator", "field_value", "raw_value", "expected"),
    [
        # equals / not equals — string and numeric coercion
        ("equals", "5", "5", True),
        ("equals", 5, "5", True),
        ("equals", "abc", "xyz", False),
        ("not equals", "abc", "xyz", True),
        ("not equals", 5, "5", False),
        # contains / does not contain
        ("contains", "hello world", "world", True),
        ("contains", ["a", "b", "c"], "b", True),
        ("contains", "hello", "xyz", False),
        ("does not contain", "hello", "xyz", True),
        # starts with / ends with
        ("starts with", "hello", "he", True),
        ("starts with", "hello", "lo", False),
        ("ends with", "hello", "lo", True),
        ("ends with", "hello", "he", False),
        # matches regex
        ("matches regex", "user-123", r"user-\d+", True),
        ("matches regex", "abc", r"^\d+$", False),
        # greater than / less than (numeric)
        ("greater than", 10, "5", True),
        ("greater than", "10", "5", True),
        ("less than", 5, "10", True),
        # greater than / less than (lexicographic fallback)
        ("greater than", "banana", "apple", True),
        ("less than", "apple", "banana", True),
        # between (inclusive)
        ("between", 5, "1,10", True),
        ("between", 1, "1,10", True),
        ("between", 10, "1,10", True),
        ("between", 11, "1,10", False),
        ("between", "abc", "1,10", False),
        # in / not in
        ("in", "x", "a, b, x", True),
        ("in", "z", "a, b, x", False),
        ("not in", "z", "a, b, x", True),
        # is empty / is not empty
        ("is empty", None, "", True),
        ("is empty", "", "", True),
        ("is empty", [], "", True),
        ("is empty", {}, "", True),
        ("is empty", "x", "", False),
        ("is empty", 0, "", False),  # 0 is NOT empty
        ("is not empty", "x", "", True),
        ("is not empty", None, "", False),
    ],
)
def test_evaluate_operators(operator, field_value, raw_value, expected):
    assert evaluate(operator, field_value, raw_value) is expected


def test_evaluate_unknown_operator_raises():
    with pytest.raises(KeyError):
        evaluate("does not exist", "x", "y")


def test_missing_field_all_comparisons_false_except_is_empty():
    assert evaluate("equals", MISSING, "x") is False
    assert evaluate("contains", MISSING, "x") is False
    assert evaluate("greater than", MISSING, "5") is False
    assert evaluate("is empty", MISSING, "") is True
    assert evaluate("is not empty", MISSING, "") is False


def test_operators_dict_lists_all_14():
    assert set(OPERATORS) == {
        "equals", "not equals",
        "contains", "does not contain",
        "starts with", "ends with",
        "matches regex",
        "greater than", "less than",
        "between",
        "in", "not in",
        "is empty", "is not empty",
    }

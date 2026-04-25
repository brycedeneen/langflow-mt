"""Shared helpers for FilterRecords and CombineRecords.

Private to the processing bundle. Not part of the public lfx API.
"""

from __future__ import annotations

import re
from typing import Any, Final

# Sentinel returned by get_path when a field is absent. Distinct from None
# (which is a legitimate stored value).
MISSING: Final = object()

_INDEX_RE = re.compile(r"^([^\[\]]+)\[(\d+)\]$")


def get_path(record: Any, path: str) -> Any:
    """Walk a dot-separated path, supporting `[N]` list indexing.

    Returns MISSING if any segment can't be resolved.
    """
    current: Any = record
    for raw_segment in path.split("."):
        if current is None:
            return MISSING
        match = _INDEX_RE.match(raw_segment)
        if match:
            key, index_str = match.group(1), match.group(2)
            if not isinstance(current, dict) or key not in current:
                return MISSING
            container = current[key]
            if not isinstance(container, list):
                return MISSING
            index = int(index_str)
            if index >= len(container):
                return MISSING
            current = container[index]
        else:
            if not isinstance(current, dict) or raw_segment not in current:
                return MISSING
            current = current[raw_segment]
    return current


def _coerce_float(value: Any) -> float | None:
    """Try to coerce to float. Return None on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_empty(value: Any) -> bool:
    """True for None, "", [], {}, MISSING. Note: 0 and False are NOT empty."""
    if value is MISSING or value is None:
        return True
    if isinstance(value, (str, list, dict, tuple, set)):
        return len(value) == 0
    return False


def _op_equals(a: Any, b: str) -> bool:
    if a is MISSING:
        return False
    a_num, b_num = _coerce_float(a), _coerce_float(b)
    if a_num is not None and b_num is not None:
        return a_num == b_num
    return str(a) == str(b)


def _op_contains(a: Any, b: str) -> bool:
    if a is MISSING:
        return False
    if isinstance(a, list):
        # Membership in a list: try numeric coercion of b for numeric lists.
        b_num = _coerce_float(b)
        for item in a:
            if str(item) == b:
                return True
            if b_num is not None and _coerce_float(item) == b_num:
                return True
        return False
    return b in str(a)


def _op_starts_with(a: Any, b: str) -> bool:
    return False if a is MISSING else str(a).startswith(b)


def _op_ends_with(a: Any, b: str) -> bool:
    return False if a is MISSING else str(a).endswith(b)


def _op_regex(a: Any, b: str) -> bool:
    return False if a is MISSING else re.search(b, str(a)) is not None


def _op_gt(a: Any, b: str) -> bool:
    if a is MISSING:
        return False
    a_num, b_num = _coerce_float(a), _coerce_float(b)
    if a_num is not None and b_num is not None:
        return a_num > b_num
    try:
        return str(a) > str(b)
    except TypeError:
        return False


def _op_lt(a: Any, b: str) -> bool:
    if a is MISSING:
        return False
    a_num, b_num = _coerce_float(a), _coerce_float(b)
    if a_num is not None and b_num is not None:
        return a_num < b_num
    try:
        return str(a) < str(b)
    except TypeError:
        return False


def _op_between(a: Any, b: str) -> bool:
    if a is MISSING:
        return False
    parts = [p.strip() for p in b.split(",")]
    if len(parts) != 2:
        return False
    lo, hi = _coerce_float(parts[0]), _coerce_float(parts[1])
    a_num = _coerce_float(a)
    if lo is None or hi is None or a_num is None:
        return False
    return lo <= a_num <= hi


def _op_in(a: Any, b: str) -> bool:
    if a is MISSING:
        return False
    options = [p.strip() for p in b.split(",")]
    a_str = str(a)
    if a_str in options:
        return True
    a_num = _coerce_float(a)
    if a_num is not None:
        for opt in options:
            opt_num = _coerce_float(opt)
            if opt_num is not None and a_num == opt_num:
                return True
    return False


OPERATORS: Final[dict[str, Any]] = {
    "equals": _op_equals,
    "not equals": lambda a, b: not _op_equals(a, b) if a is not MISSING else False,
    "contains": _op_contains,
    "does not contain": lambda a, b: not _op_contains(a, b) if a is not MISSING else False,
    "starts with": _op_starts_with,
    "ends with": _op_ends_with,
    "matches regex": _op_regex,
    "greater than": _op_gt,
    "less than": _op_lt,
    "between": _op_between,
    "in": _op_in,
    "not in": lambda a, b: not _op_in(a, b) if a is not MISSING else False,
    "is empty": lambda a, _b: _is_empty(a),
    "is not empty": lambda a, _b: not _is_empty(a),
}


def evaluate(operator: str, field_value: Any, raw_value: str) -> bool:
    """Evaluate one operator against a field value and a raw user value.

    Raises KeyError if `operator` is not a recognized operator name.
    """
    return OPERATORS[operator](field_value, raw_value)

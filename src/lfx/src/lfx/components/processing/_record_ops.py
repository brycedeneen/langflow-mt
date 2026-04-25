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

"""Row orchestration + output packaging for DataMapperComponent."""

from __future__ import annotations

import logging
import types
from datetime import date, datetime
from typing import Any, Callable

from lfx.components.processing._data_mapper.config_schema import DestFieldDef, MapperConfig
from lfx.components.processing._data_mapper.join import build_index, lookup as join_lookup
from lfx.components.processing._data_mapper.transforms import _MISSING, dispatch

logger = logging.getLogger(__name__)

VariableResolver = Callable[[str], Any]


_TYPE_BLANK: dict[str, Any] = {
    "str": "",
    "int": None,
    "float": None,
    "bool": False,
    "list": [],
    "dict": {},
    "date": None,
    "datetime": None,
}


def _normalize_input(raw: Any) -> list[dict[str, Any]]:
    """Accept a single record or a list of records; always return list[dict]."""
    if raw is None:
        return []
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)]
    msg = f"input must be dict or list[dict], got {type(raw).__name__}"
    raise TypeError(msg)


def _coerce(value: Any, target_type: str) -> Any:
    """Best-effort type coercion. On failure, return the raw value and warn."""
    if value is None:
        return value
    try:
        if target_type == "str":
            return value if isinstance(value, str) else str(value)
        if target_type == "int":
            return int(value) if not isinstance(value, bool) else int(value)
        if target_type == "float":
            return float(value)
        if target_type == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in {"true", "1", "yes"}
            return bool(value)
        if target_type == "list":
            return value if isinstance(value, list) else [value]
        if target_type == "dict":
            if isinstance(value, dict):
                return value
            msg = "cannot coerce non-dict to dict"
            raise ValueError(msg)
        if target_type in ("date", "datetime"):
            if isinstance(value, (date, datetime)):
                return value
            if isinstance(value, str):
                return datetime.fromisoformat(value)
    except (ValueError, TypeError) as e:
        logger.warning("type coercion to %s failed for %r: %s", target_type, value, e)
        return value
    return value


def _resolve_missing(raw: Any, dest: DestFieldDef) -> tuple[Any, bool]:
    """Apply required/default logic. Returns (value, had_required_error)."""
    if raw is not _MISSING:
        return raw, False

    if dest.default is not None:
        fallback = dest.default
    else:
        fallback = _TYPE_BLANK.get(dest.type)

    if dest.required:
        logger.warning("required destination field '%s' was missing; emitting default", dest.name)
        return fallback, True
    return fallback, False


def _build_row_context(
    driver_row: dict[str, Any],
    driver_alias: str,
    lookup_rows: dict[str, dict[str, Any] | None],
) -> dict[str, Any]:
    """Flatten driver fields to top-level; expose lookups as dot-accessible namespaces.

    - Driver fields are flattened to top-level for template/expression access.
    - Driver alias maps to a SimpleNamespace of the driver row (dot-access in expressions).
    - Lookup aliases map to SimpleNamespace wrappers (or None if unmatched), enabling
      dot-notation in expression transforms (e.g. ``jobs.salary * 1.1``).
    """
    ctx: dict[str, Any] = dict(driver_row)
    ctx[driver_alias] = types.SimpleNamespace(**driver_row)
    for alias, row in lookup_rows.items():
        ctx[alias] = types.SimpleNamespace(**row) if row else None
    return ctx


def run(
    config: MapperConfig,
    inputs: list[Any],
    *,
    variable_resolver: VariableResolver,
) -> list[dict[str, Any]]:
    """Execute the mapping engine. Returns list of output records."""
    if len(inputs) != len(config.inputs):
        msg = f"expected {len(config.inputs)} inputs, got {len(inputs)}"
        raise ValueError(msg)

    # Normalize each input to list[dict]
    normalized = [_normalize_input(raw) for raw in inputs]

    driver_rows = normalized[config.driver_index]

    # Build lookup indexes for non-driver inputs
    lookup_indexes: dict[str, dict[tuple, dict[str, Any]]] = {}
    for idx, inp in enumerate(config.inputs):
        if idx == config.driver_index:
            continue
        assert inp.join is not None  # guaranteed by config validator
        index, collisions = build_index(normalized[idx], inp.join)
        lookup_indexes[inp.alias] = index
        if collisions > 0:
            logger.warning(
                "lookup '%s' had %d duplicate key(s); first-match-wins",
                inp.alias,
                collisions,
            )

    driver_alias = config.inputs[config.driver_index].alias

    # Index mappings by destination for quick lookup
    mappings_by_dest = {m.destination: m for m in config.mappings}

    output_rows: list[dict[str, Any]] = []
    for driver_row in driver_rows:
        # Resolve lookups for this driver row
        lookup_rows: dict[str, dict[str, Any] | None] = {}
        for idx, inp in enumerate(config.inputs):
            if idx == config.driver_index:
                continue
            assert inp.join is not None
            lookup_rows[inp.alias] = join_lookup(
                lookup_indexes[inp.alias], driver_row, inp.join
            )

        ctx = _build_row_context(driver_row, driver_alias, lookup_rows)

        output_row: dict[str, Any] = {}
        for dest in config.destination_schema:
            mapping = mappings_by_dest.get(dest.name)
            if mapping is None:
                raw = _MISSING
            else:
                # transforms.dispatch expects a plain dict, not a Pydantic model
                raw = dispatch(
                    mapping.model_dump(),
                    ctx,
                    variable_resolver=variable_resolver,
                )
            value, _had_err = _resolve_missing(raw, dest)
            if value is not None:
                value = _coerce(value, dest.type)
            output_row[dest.name] = value
        output_rows.append(output_row)

    return output_rows

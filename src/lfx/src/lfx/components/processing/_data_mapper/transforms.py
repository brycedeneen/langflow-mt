"""Per-field transform evaluators for DataMapperComponent."""

from __future__ import annotations

from typing import Any, Callable


class _MissingType:
    """Singleton sentinel indicating an absent source value.

    Distinct from `None`: `None` is an explicit null emitted by the source;
    `_MISSING` means the field was never present.
    """

    _instance: "_MissingType | None" = None

    def __new__(cls) -> "_MissingType":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "_MISSING"


_MISSING: _MissingType = _MissingType()


VariableResolver = Callable[[str], Any]


def dispatch(
    mapping: dict[str, Any],
    ctx: dict[str, Any],
    *,
    variable_resolver: VariableResolver,
) -> Any:
    """Evaluate a single mapping entry against the row context.

    Returns the raw value (may be `_MISSING`). The caller applies required/default logic.
    """
    transform_type = mapping["transform"]

    if transform_type not in _DISPATCH:
        msg = f"unknown transform type: {transform_type!r}"
        raise ValueError(msg)

    return _DISPATCH[transform_type](mapping, ctx, variable_resolver=variable_resolver)


def _eval_direct(mapping: dict[str, Any], ctx: dict[str, Any], **_: Any) -> Any:
    sources = mapping.get("sources") or []
    if len(sources) != 1:
        msg = f"'direct' transform requires exactly 1 source, got {len(sources)}"
        raise ValueError(msg)
    src = sources[0]
    input_alias = src["input"]
    field = src["field"]
    if input_alias not in ctx:
        return _MISSING
    row = ctx[input_alias]
    if row is None:
        return _MISSING
    if field not in row:
        return _MISSING
    return row[field]


def _eval_static(mapping: dict[str, Any], ctx: dict[str, Any], **_: Any) -> Any:
    config = mapping.get("config") or {}
    if "value" not in config:
        msg = "'static' transform requires config.value"
        raise ValueError(msg)
    return config["value"]


_DISPATCH: dict[str, Callable[..., Any]] = {
    "direct": _eval_direct,
    "static": _eval_static,
}

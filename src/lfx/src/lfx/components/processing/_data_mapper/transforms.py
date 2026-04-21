"""Per-field transform evaluators for DataMapperComponent."""

from __future__ import annotations

from typing import Any, Callable

import jinja2
from asteval import Interpreter


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


_JINJA_ENV = jinja2.Environment(
    undefined=jinja2.ChainableUndefined,
    autoescape=False,
    keep_trailing_newline=False,
)


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


def _eval_variable(
    mapping: dict[str, Any],
    ctx: dict[str, Any],
    *,
    variable_resolver: VariableResolver,
) -> Any:
    config = mapping.get("config") or {}
    name = config.get("variable")
    if not name:
        msg = "'variable' transform requires config.variable (name)"
        raise ValueError(msg)
    result = variable_resolver(name)
    if result is None:
        return _MISSING
    return result


def _eval_template(mapping: dict[str, Any], ctx: dict[str, Any], **_: Any) -> Any:
    config = mapping.get("config") or {}
    template_str = config.get("template")
    if template_str is None:
        msg = "'template' transform requires config.template"
        raise ValueError(msg)
    template = _JINJA_ENV.from_string(template_str)
    return template.render(**ctx)


_FORBIDDEN_EXPR_TOKENS = ("__", "import ", "from ")


def _eval_expression(mapping: dict[str, Any], ctx: dict[str, Any], **_: Any) -> Any:
    config = mapping.get("config") or {}
    expression_str = config.get("expression")
    if expression_str is None:
        msg = "'expression' transform requires config.expression"
        raise ValueError(msg)

    # Coarse pre-filter — blocks dunder access and import statements before asteval sees them.
    # asteval already blocks imports in the interpreter, but this gives a cleaner error earlier
    # and catches dunder attribute access that asteval may or may not block depending on version.
    for token in _FORBIDDEN_EXPR_TOKENS:
        if token in expression_str:
            msg = f"'expression' transform disallows token {token!r}: {expression_str!r}"
            raise ValueError(msg)

    interp = Interpreter(
        use_numpy=False,
        minimal=False,
        readonly_symbols=set(ctx.keys()),
    )
    # Preload context as readonly.
    for k, v in ctx.items():
        interp.symtable[k] = v

    result = interp.eval(expression_str, show_errors=False, raise_errors=False)
    if interp.error:
        # asteval collects errors without raising by default; surface them as ValueError.
        err_msg = interp.error[0].get_error()
        msg = f"'expression' transform failed: {err_msg[0] if isinstance(err_msg, tuple) else err_msg}"
        raise ValueError(msg)
    return result


def _eval_array(mapping: dict[str, Any], ctx: dict[str, Any], **_: Any) -> Any:
    sources = mapping.get("sources") or []
    config = mapping.get("config") or {}
    skip_missing = bool(config.get("skip_missing", False))

    result: list[Any] = []
    for src in sources:
        input_alias = src["input"]
        field = src["field"]
        if input_alias not in ctx:
            value = _MISSING
        else:
            row = ctx[input_alias]
            if row is None:
                value = _MISSING
            elif field not in row:
                value = _MISSING
            else:
                value = row[field]

        if value is _MISSING:
            if skip_missing:
                continue
            result.append(None)
        else:
            result.append(value)
    return result


_DISPATCH: dict[str, Callable[..., Any]] = {
    "direct": _eval_direct,
    "static": _eval_static,
    "variable": _eval_variable,
    "template": _eval_template,
    "expression": _eval_expression,
    "array": _eval_array,
}

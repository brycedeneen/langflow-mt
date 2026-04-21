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


def _template(template_str):
    return {
        "transform": "template",
        "sources": [],
        "config": {"template": template_str},
    }


def test_template_renders_driver_fields():
    ctx = {"workers": {"first_name": "Ada", "last_name": "Lovelace"}}
    # Convention: driver fields are flattened into context top-level.
    # The engine passes a flattened-ctx view to template; here we test that
    # the transform reads from the flattened view it receives.
    flat = {"first_name": "Ada", "last_name": "Lovelace"}
    assert (
        dispatch(_template("{{ first_name }} {{ last_name }}"), flat, variable_resolver=lambda n: None)
        == "Ada Lovelace"
    )


def test_template_undefined_renders_as_empty_string():
    flat = {"first_name": "Ada"}
    assert dispatch(_template("{{ first_name }} {{ missing }}"), flat, variable_resolver=lambda n: None) == "Ada "


def test_template_supports_filters():
    flat = {"name": "ada"}
    assert dispatch(_template("{{ name | upper }}"), flat, variable_resolver=lambda n: None) == "ADA"


def test_template_lookup_attribute_access():
    # Lookups are exposed as SimpleNamespace-like: jobs.title
    import types
    flat = {"jobs": types.SimpleNamespace(title="Engineer")}
    assert dispatch(_template("{{ jobs.title }}"), flat, variable_resolver=lambda n: None) == "Engineer"


def test_template_requires_config_template():
    mapping = {"transform": "template", "sources": [], "config": {}}
    with pytest.raises(ValueError, match="config.template"):
        dispatch(mapping, {}, variable_resolver=lambda n: None)


def _expr(expression_str):
    return {
        "transform": "expression",
        "sources": [],
        "config": {"expression": expression_str},
    }


def test_expression_arithmetic():
    flat = {"x": 10, "y": 3}
    assert dispatch(_expr("x + y"), flat, variable_resolver=lambda n: None) == 13


def test_expression_multiplication_and_precedence():
    flat = {"price": 100, "tax_rate": 0.08}
    assert dispatch(_expr("price * (1 + tax_rate)"), flat, variable_resolver=lambda n: None) == pytest.approx(108.0)


def test_expression_boolean_ternary():
    flat = {"country": "FR"}
    assert (
        dispatch(_expr("'EMEA' if country in ['FR','DE','UK'] else 'US'"), flat, variable_resolver=lambda n: None)
        == "EMEA"
    )


def test_expression_comprehension():
    flat = {"invoices": [{"amt": 10}, {"amt": 20}, {"amt": 30}]}
    assert dispatch(_expr("[i['amt'] for i in invoices]"), flat, variable_resolver=lambda n: None) == [10, 20, 30]


def test_expression_rejects_import():
    flat = {}
    with pytest.raises(ValueError, match="expression"):
        dispatch(_expr("__import__('os').system('echo hi')"), flat, variable_resolver=lambda n: None)


def test_expression_rejects_dunder_access():
    flat = {"x": 1}
    with pytest.raises(ValueError, match="expression"):
        dispatch(_expr("x.__class__"), flat, variable_resolver=lambda n: None)


def test_expression_requires_config_expression():
    mapping = {"transform": "expression", "sources": [], "config": {}}
    with pytest.raises(ValueError, match="config.expression"):
        dispatch(mapping, {}, variable_resolver=lambda n: None)


def test_expression_syntax_error_raises_value_error():
    flat = {}
    with pytest.raises(ValueError, match="expression"):
        dispatch(_expr("x ++"), flat, variable_resolver=lambda n: None)

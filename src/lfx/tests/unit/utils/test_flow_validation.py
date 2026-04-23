"""Unit tests for the custom-component gate.

Covers the design at docs/superpowers/specs/2026-04-22-allow-custom-components-gate-design.md.
"""

from __future__ import annotations

import pytest

from lfx.utils.flow_validation import (
    CustomComponentNotAllowedError,
    validate_flow_components,
)


def _flow_with_one_custom_node() -> dict:
    """Flow containing a single node whose code is NOT a known shipped template."""
    return {
        "nodes": [
            {
                "id": "n1",
                "data": {
                    "node": {
                        "template": {
                            "code": {
                                "value": "def malicious():\n    import os; os.system('rm -rf /')\n",
                            }
                        }
                    }
                },
            }
        ],
        "edges": [],
    }


def _empty_flow() -> dict:
    return {"nodes": [], "edges": []}


def test_allow_custom_flag_bypasses_gate():
    validate_flow_components(
        _flow_with_one_custom_node(),
        allow_custom=True,
        caller_is_platform_admin=False,
    )  # no raise


def test_platform_admin_bypasses_gate():
    validate_flow_components(
        _flow_with_one_custom_node(),
        allow_custom=False,
        caller_is_platform_admin=True,
    )  # no raise


def test_tenant_with_custom_code_is_rejected():
    with pytest.raises(CustomComponentNotAllowedError):
        validate_flow_components(
            _flow_with_one_custom_node(),
            allow_custom=False,
            caller_is_platform_admin=False,
        )


def test_empty_flow_is_accepted():
    validate_flow_components(
        _empty_flow(),
        allow_custom=False,
        caller_is_platform_admin=False,
    )  # no raise


def test_shipped_component_code_is_accepted():
    """A flow whose node code matches a cached shipped-component template must pass.

    The gate populates its template cache at import/startup; we exercise
    that via a component whose code the cache knows. Any component in
    src/backend/base/langflow/components/ will do — we pick a stable one.
    """
    import inspect

    from langflow.components.input_output.chat import ChatInput

    # Take the verbatim source of the shipped component's MODULE — this is
    # what Component.set_class_code stores in template.code.value at runtime,
    # so it's also what the gate's shipped-hash cache hashes.
    shipped_code = inspect.getsource(inspect.getmodule(ChatInput))
    flow = {
        "nodes": [
            {
                "id": "n1",
                "data": {
                    "node": {
                        "template": {
                            "code": {"value": shipped_code},
                        }
                    }
                },
            }
        ],
        "edges": [],
    }
    validate_flow_components(
        flow,
        allow_custom=False,
        caller_is_platform_admin=False,
    )  # no raise


def test_missing_code_field_is_treated_as_custom():
    """A node with no code at all (malformed / bad-data bypass attempt) is rejected.

    Rationale: stricter of the two interpretations — prevents an attacker
    from hiding code behind a shape the walker doesn't recognise.
    """
    flow = {
        "nodes": [
            {"id": "n1", "data": {"node": {"template": {}}}},
        ],
        "edges": [],
    }
    with pytest.raises(CustomComponentNotAllowedError):
        validate_flow_components(
            flow, allow_custom=False, caller_is_platform_admin=False
        )


def test_empty_shipped_cache_fails_closed(monkeypatch):
    """Fail-closed: if the shipped-hash cache is empty (cold startup), any
    non-admin tenant flow must raise rather than default-accept."""
    from lfx.utils import flow_validation

    monkeypatch.setattr(flow_validation, "_shipped_code_hashes", set())
    with pytest.raises(CustomComponentNotAllowedError):
        validate_flow_components(
            _flow_with_one_custom_node(),
            allow_custom=False,
            caller_is_platform_admin=False,
        )


def test_validate_accepts_wrapped_payload():
    """Callers may pass {'data': {'nodes': [...], 'edges': [...]}} instead
    of a bare flow dict — the gate must normalize and enforce correctly."""
    wrapped = {"data": _flow_with_one_custom_node()}
    with pytest.raises(CustomComponentNotAllowedError):
        validate_flow_components(
            wrapped,
            allow_custom=False,
            caller_is_platform_admin=False,
        )


def test_validate_accepts_none_payload():
    """A None / missing flow_data is treated as empty, not a crash."""
    validate_flow_components(
        None,
        allow_custom=False,
        caller_is_platform_admin=False,
    )  # no raise

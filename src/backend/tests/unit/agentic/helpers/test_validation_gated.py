"""Regression: agentic validation must not exec() LLM-generated code unless
the LANGFLOW_ALLOW_CUSTOM_COMPONENTS gate is open (or the caller is a
platform admin).

Covers CVE-2026-33873 (GHSA-v8hw-mh8c-jxfc). Fork-specific mitigation — see
docs/superpowers/plans/2026-04-23-security-advisory-backport.md Task 4.
"""

from __future__ import annotations

from unittest.mock import patch

from langflow.agentic.helpers.validation import validate_component_code


# A class definition whose `__init__` would raise at runtime — if create_class
# + instantiation fires, we'll see that runtime error; if we're AST-only, the
# value is simply `is_valid=True, executed=False`.
_BOOM_CODE = '''
from langflow.custom import Component

class Boom(Component):
    def __init__(self):
        raise RuntimeError("detonated at runtime — we should never see this when gated off")
'''


def test_validation_gated_off_does_not_exec():
    """With allow_custom_components=False and caller not a platform admin,
    validate_component_code must NOT call create_class/exec. Detect by
    ensuring the deliberate runtime error in __init__ does NOT surface."""
    with patch(
        "langflow.agentic.helpers.validation.create_class"
    ) as mock_create_class:
        result = validate_component_code(
            _BOOM_CODE,
            allow_custom_components=False,
            caller_is_platform_admin=False,
        )
        mock_create_class.assert_not_called()
        assert result.is_valid is True
        assert result.executed is False
        assert result.class_name == "Boom"


def test_validation_gated_off_rejects_syntax_errors():
    """AST-only mode still refuses genuinely broken code."""
    result = validate_component_code(
        "class Broken(:\n    pass",  # syntax error
        allow_custom_components=False,
        caller_is_platform_admin=False,
    )
    assert result.is_valid is False
    assert result.executed is False


def test_validation_gate_allows_when_flag_on():
    """When deployment opts in, original behavior resumes."""
    # Use a benign class — just assert create_class was called.
    benign = '''
from langflow.custom import Component

class Benign(Component):
    def __init__(self):
        super().__init__()
'''
    with patch(
        "langflow.agentic.helpers.validation.create_class"
    ) as mock_create_class:
        # Make create_class return a factory that produces a no-op class.
        class _Noop:
            def __init__(self):
                pass

        mock_create_class.return_value = _Noop
        validate_component_code(
            benign,
            allow_custom_components=True,
            caller_is_platform_admin=False,
        )
        mock_create_class.assert_called_once()


def test_validation_gate_allows_for_platform_admin():
    """Platform admins bypass the gate even when the deployment flag is off."""
    benign = '''
from langflow.custom import Component

class Benign(Component):
    def __init__(self):
        super().__init__()
'''
    with patch(
        "langflow.agentic.helpers.validation.create_class"
    ) as mock_create_class:
        class _Noop:
            def __init__(self):
                pass

        mock_create_class.return_value = _Noop
        validate_component_code(
            benign,
            allow_custom_components=False,
            caller_is_platform_admin=True,
        )
        mock_create_class.assert_called_once()

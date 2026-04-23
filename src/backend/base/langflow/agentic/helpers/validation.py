"""Component code validation."""

import ast
import re

from lfx.custom.validate import create_class, extract_class_name

from langflow.agentic.api.schemas import ValidationResult

# Regex pattern to extract class name that inherits from Component
CLASS_NAME_PATTERN = re.compile(r"class\s+(\w+)\s*\([^)]*Component[^)]*\)")


def _extract_class_name_regex(code: str) -> str | None:
    """Extract class name using regex (fallback for syntax errors)."""
    match = CLASS_NAME_PATTERN.search(code)
    return match.group(1) if match else None


def _safe_extract_class_name(code: str) -> str | None:
    """Extract class name with fallback to regex for broken code."""
    try:
        return extract_class_name(code)
    except (ValueError, SyntaxError, TypeError):
        return _extract_class_name_regex(code)


def _ast_only_validate(code: str) -> ValidationResult:
    """Validate code without executing it.

    Used when the ALLOW_CUSTOM_COMPONENTS gate is closed — this is the
    multi-tenant default and the mitigation for CVE-2026-33873 (Agentic
    Assistant Validation RCE).

    Performs:
    - ``ast.parse`` to confirm syntactic validity.
    - Class-name extraction to confirm a ``class X(Component)`` declaration
      is present.

    Does NOT:
    - Import the code's referenced modules.
    - Instantiate the class (no ``__init__`` checks).
    - Call ``exec()`` on any compiled form of the user's code.
    """
    class_name = _safe_extract_class_name(code)
    try:
        ast.parse(code)
    except SyntaxError as exc:
        return ValidationResult(
            is_valid=False,
            code=code,
            class_name=class_name,
            error=f"SyntaxError: {exc}",
            executed=False,
        )
    if class_name is None:
        return ValidationResult(
            is_valid=False,
            code=code,
            class_name=None,
            error="Could not extract a Component subclass declaration",
            executed=False,
        )
    return ValidationResult(
        is_valid=True,
        code=code,
        class_name=class_name,
        executed=False,
    )


def validate_component_code(
    code: str,
    *,
    allow_custom_components: bool = False,
    caller_is_platform_admin: bool = False,
) -> ValidationResult:
    """Validate component code.

    Security: when the deployment's ``LANGFLOW_ALLOW_CUSTOM_COMPONENTS`` flag
    is off AND the caller is not a platform admin, this function performs
    AST-only validation and does NOT call ``create_class`` (which ends in
    ``exec()``). This mitigates CVE-2026-33873 — authenticated code execution
    via the Agentic Assistant's validation path — for multi-tenant deploys
    where LLM output may be attacker-influenced.

    When the gate is open (opt-in or caller is a platform admin), the full
    create-and-instantiate path runs to catch ``__init__``-time errors like
    overlapping input/output names.

    Args:
        code: Python source of the component to validate.
        allow_custom_components: Deployment-level gate flag, typically from
            ``resolve_component_gate_flags``.
        caller_is_platform_admin: True when the request's user has
            ``is_platform_admin=True``.

    Returns:
        A ``ValidationResult`` whose ``executed`` flag indicates whether the
        full create/instantiate path ran or whether validation was AST-only.
    """
    if not (allow_custom_components or caller_is_platform_admin):
        return _ast_only_validate(code)

    class_name = _safe_extract_class_name(code)

    try:
        if class_name is None:
            msg = "Could not extract class name from code"
            raise ValueError(msg)

        # create_class returns the class (not an instance)
        component_class = create_class(code, class_name)

        # Instantiate the class to trigger __init__ validation
        # This catches errors like overlapping input/output names
        component_class()

        return ValidationResult(is_valid=True, code=code, class_name=class_name, executed=True)
    except (
        ValueError,
        TypeError,
        SyntaxError,
        NameError,
        ModuleNotFoundError,
        AttributeError,
        ImportError,
        RuntimeError,
        KeyError,
    ) as e:
        return ValidationResult(
            is_valid=False,
            code=code,
            error=f"{type(e).__name__}: {e}",
            class_name=class_name,
            executed=True,
        )

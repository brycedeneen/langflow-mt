"""Extract metadata from a Component class for LLM synthesis."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class InputMetadata:
    name: str
    info: str | None
    field_type: str | None = None
    required: bool = False
    advanced: bool = False


@dataclass(frozen=True)
class ComponentMetadata:
    class_name: str
    display_name: str
    description: str
    documentation: str | None
    docstring: str
    inputs: list[InputMetadata] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)


def _safe_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _input_field_type(raw: Any) -> str | None:
    """Prefer an explicit ``field_type`` attribute; fall back to the Python class name."""
    explicit = getattr(raw, "field_type", None)
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    cls = type(raw)
    return cls.__name__ if cls is not object else None


def extract_metadata(component_cls: type) -> ComponentMetadata:
    class_name = component_cls.__name__
    display_name = _safe_str(getattr(component_cls, "display_name", ""))
    description = _safe_str(getattr(component_cls, "description", ""))
    documentation = _safe_str(getattr(component_cls, "documentation", "")) or None
    docstring = _safe_str(component_cls.__doc__ or "")

    inputs: list[InputMetadata] = []
    for raw in getattr(component_cls, "inputs", []) or []:
        name = getattr(raw, "name", None) or ""
        info = getattr(raw, "info", None)
        if name:
            inputs.append(
                InputMetadata(
                    name=name,
                    info=info if isinstance(info, str) else None,
                    field_type=_input_field_type(raw),
                    required=bool(getattr(raw, "required", False)),
                    advanced=bool(getattr(raw, "advanced", False)),
                )
            )

    outputs: list[str] = []
    for raw in getattr(component_cls, "outputs", []) or []:
        name = getattr(raw, "name", None)
        if isinstance(name, str) and name:
            outputs.append(name)

    return ComponentMetadata(
        class_name=class_name,
        display_name=display_name,
        description=description,
        documentation=documentation,
        docstring=docstring,
        inputs=inputs,
        outputs=outputs,
    )


def metadata_completeness(meta: ComponentMetadata) -> Literal["rich", "thin"]:
    """Heuristic: flag components unlikely to yield a useful guide from metadata alone."""
    has_description = bool(meta.description) or bool(meta.docstring)
    has_input_info = any(i.info for i in meta.inputs)
    return "rich" if (has_description and (has_input_info or not meta.inputs)) else "thin"

"""Model configuration and validation helpers for Agentics components."""

from __future__ import annotations

from typing import Any

from lfx.components.agentics.constants import (
    ERROR_MODEL_NOT_SELECTED,
    PROVIDER_OLLAMA,
)


def validate_model_selection(model: Any) -> tuple[str, str]:
    """Validate and extract model name and provider from component input.

    Ensures the model selection is properly formatted and contains required fields.

    Args:
        model: The model selection from the component input (expected as a list with model dict).

    Returns:
        Tuple of (model_name, provider) extracted from the selection.

    Raises:
        ValueError: If no model is selected, model data is invalid, or required fields are missing.
    """
    if not model or not isinstance(model, list) or len(model) == 0:
        raise ValueError(ERROR_MODEL_NOT_SELECTED)

    model_selection = model[0]

    model_name = model_selection.get("name")
    provider = model_selection.get("provider")

    if not model_name or not provider:
        raise ValueError(ERROR_MODEL_NOT_SELECTED)

    return model_name, provider


def update_provider_fields_visibility(
    build_config: dict,
    field_value: Any,
    field_name: str | None,
) -> dict:
    """Update visibility of provider-specific fields based on the selected model.

    Dynamically shows/hides fields like Ollama base_url depending on which
    provider is currently selected.

    Args:
        build_config: The build configuration dictionary to update.
        field_value: The current field value being processed.
        field_name: The name of the field being updated (e.g., "model").

    Returns:
        Updated build configuration with adjusted field visibility.
    """
    current_model_value = field_value if field_name == "model" else build_config.get("model", {}).get("value")

    if not isinstance(current_model_value, list) or len(current_model_value) == 0:
        return build_config

    selected_model = current_model_value[0]
    provider = selected_model.get("provider", "")

    _update_ollama_fields(build_config, provider)

    return build_config


def _update_ollama_fields(build_config: dict, provider: str) -> None:
    """Update visibility for Ollama-specific fields.

    Shows ollama_base_url field only when Ollama is selected.
    """
    is_ollama = provider == PROVIDER_OLLAMA

    if "ollama_base_url" in build_config:
        build_config["ollama_base_url"]["show"] = is_ollama

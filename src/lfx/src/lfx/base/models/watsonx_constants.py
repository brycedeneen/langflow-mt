"""Compatibility shim — IBM WatsonX is being removed (Phase 1).

The actual constants and helpers have been deleted; this file exists solely to
keep module-level `from lfx.base.models.watsonx_constants import …` statements
in downstream files resolvable while Phase 2 migrates each caller off the
symbol. All exports are empty / no-op; any code path that reaches this module
at runtime will get no WatsonX options surfaced to the user.

Remove this file once Phase 2 (removing watsonx references from
unified_models.py, model_input_constants.py, model_metadata.py, tool_calling.py,
agentics/*, langchain_utilities/*, services/settings/constants.py, and the
models_and_agents/{agent,language_model,embedding_model}.py form inputs) lands.
"""

from __future__ import annotations

WATSONX_DEFAULT_LLM_MODELS: list[dict] = []
WATSONX_DEFAULT_EMBEDDING_MODELS: list[dict] = []
WATSONX_EMBEDDING_MODELS_DETAILED: list[dict] = []
WATSONX_MODELS_DETAILED: list[dict] = []
WATSONX_EMBEDDING_MODEL_NAMES: list[str] = []
# Single placeholder entry so any consumer doing IBM_WATSONX_URLS[0] during form
# construction doesn't crash on an empty list. Runtime WatsonX flows are gone.
IBM_WATSONX_URLS: list[str] = [""]

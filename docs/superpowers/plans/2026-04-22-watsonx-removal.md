# IBM WatsonX Removal — Phased Plan

**Date:** 2026-04-22
**Status:** Phase 1 landed; Phases 2–5 pending.
**Goal:** Remove all first-party IBM WatsonX / Granite / `langchain-ibm` support from Langflow. WatsonX is already excluded from production deploy via a pandas override stopgap; this work finishes the removal so the stopgap can go.

## Phase 1 — landed 2026-04-22

Direct source deletions:
- `src/lfx/src/lfx/components/ibm/` (entire dir — WatsonxAIComponent, WatsonxEmbeddingsComponent)
- `src/lfx/tests/unit/components/ibm/` (entire dir)
- `src/backend/tests/unit/integration_smoke/test_pandas_3_overrides_watsonx.py`
- `src/backend/tests/unit/components/models_and_agents/test_ibm_granite_handler.py`
- `src/frontend/src/icons/IBM/` (entire dir — IBMIcon, WatsonxAiIcon, SVG)

Pyproject deps removed (direct):
- `ibm-watsonx-ai>=1.3.1,<2.0.0`
- `langchain-ibm>=0.3.8,<1.0.0`

Note: both packages remain in `uv.lock` because `agent-lifecycle-toolkit` (ALTK,
currently pinned at `~=0.4.4`) pulls them in transitively. Getting them out of
the lock entirely is an ALTK concern, not a Langflow one.

Registry / import-chain surgery:
- `src/lfx/src/lfx/components/__init__.py` — removed `ibm` from the import list, the
  `"ibm": "__module__"` registry entry, and the `"ibm"` name in `__all__`
- `src/lfx/src/lfx/base/models/model_utils.py` — removed `get_watsonx_llm_models`,
  `get_watsonx_embedding_models`, `fetch_live_watsonx_models`, and the WatsonX
  branch of `get_live_models_for_provider`
- `src/lfx/src/lfx/base/models/__init__.py` — dropped the watsonx helper re-exports
- Frontend cleanup:
  - `providerConstants.ts` — removed the `"IBM WatsonX": "WATSONX_APIKEY"` mapping
    and updated the docstring
  - `modelProviderModal/components/ProviderConfigurationForm.tsx` — removed the
    `"IBM watsonx": { prefix: "", totalLength: 44 }` key-preview entry
  - `utils/styleUtils.ts` — removed `{ display_name: "IBM", name: "ibm", icon: "WatsonxAI" }`
  - `icons/eagerIconImports.ts` + `icons/lazyIconImports.ts` — removed IBM / WatsonxAI
    registrations (import, registry entries)
  - `controllers/API/queries/models/use-get-model-providers.ts` — removed the
    `"IBM WatsonX"` / `"IBM watsonx.ai"` icon-name mappings
  - `controllers/API/queries/models/use-get-provider-variables.ts` — trimmed the
    docstring example
  - `pages/MainPage/pages/knowledgePage/config/knowledgeBaseColumns.tsx` — removed
    the `"IBM WatsonX": "WatsonxAI"` icon mapping

### Compatibility shims (delete in Phase 2)

Two modules were stubbed rather than deleted, because ~25 downstream files still
have module-level `from lfx.base.models.watsonx_constants import …` or
`from lfx.components.langchain_utilities.ibm_granite_handler import …`
statements that would crash on import:

- `src/lfx/src/lfx/base/models/watsonx_constants.py` — now exports empty lists for
  `WATSONX_DEFAULT_LLM_MODELS`, `WATSONX_DEFAULT_EMBEDDING_MODELS`,
  `WATSONX_EMBEDDING_MODELS_DETAILED`, `WATSONX_MODELS_DETAILED`,
  `WATSONX_EMBEDDING_MODEL_NAMES`. Exports `IBM_WATSONX_URLS = [""]` (single
  sentinel so `IBM_WATSONX_URLS[0]` at form-construction time doesn't IndexError).
- `src/lfx/src/lfx/components/langchain_utilities/ibm_granite_handler.py` — now
  exports no-op `is_watsonx_model`, `is_granite_model` (both return `False`),
  `get_enhanced_system_prompt` (pass-through), and `create_granite_agent` (raises
  RuntimeError if ever called — it can't be, since `is_granite_model` is now False).

Both shims carry a module-level docstring calling out that they exist solely
to keep Phase 2 sites compiling.

**Verified:** `uv sync --all-extras` installs cleanly; 77 tests pass
(`test_load_components.py` + `services/database/`). No multi-tenant regressions.

---

## Phase 2 — remove watsonx references from the model/agent layer

Each file below has module-level imports or logic that treats WatsonX as one
provider among many. Surgery is per-file — the pattern is "remove the import
from watsonx_constants, remove the form inputs / provider branches, remove
the dict entries." After this phase the `watsonx_constants.py` shim can be
deleted.

- `src/lfx/src/lfx/base/models/unified_models.py` — biggest. Remove:
  - `from lfx.base.models.watsonx_constants import WATSONX_MODELS_DETAILED` (line ~34)
  - `"ChatWatsonx"` and `"WatsonxEmbeddings"` entries from the class-lookup dicts
  - The `"IBM WatsonX"` and `"IBM watsonx.ai"` alias mappings
  - The `WATSONX_MODELS_DETAILED` spread in `get_models_detailed()` (~line 187)
  - `"IBM WatsonX"` entry from `get_provider_all_variables` and
    `get_provider_required_variable_keys`
  - The `elif provider == "IBM WatsonX":` branch in whichever function uses
    `from langchain_ibm import ChatWatsonx` (~line 792)
  - The `"IBM WatsonX"` key in the provider metadata dict (~line 1272)
  - `watsonx_url` / `watsonx_project_id` kwargs wherever they appear (~1455)
- `src/lfx/src/lfx/base/models/model_metadata.py` — remove any `IBM WatsonX`
  defaults/metadata
- `src/lfx/src/lfx/base/models/model_input_constants.py` — the `_get_watsonx_inputs_and_fields`
  function and the `try: from lfx.components.ibm.watsonx import …` block at the
  bottom are already gated by try/except ImportError, so they short-circuit cleanly
  in Phase 1. They should still be deleted for cleanliness.
- `src/lfx/src/lfx/components/models_and_agents/language_model.py` — remove the
  `IBM_WATSONX_URLS` import + the `base_url_ibm_watsonx` dropdown + the watsonx
  show/hide logic
- `src/lfx/src/lfx/components/models_and_agents/embedding_model.py` — same pattern
- `src/lfx/src/lfx/components/models_and_agents/agent.py` — same
- `src/lfx/src/lfx/components/llm_operations/batch_run.py` — check for watsonx refs
- `src/lfx/src/lfx/services/settings/constants.py` — check for `WATSONX_*` env var
  declarations; remove them

## Phase 3 — remove watsonx references from agentics + langchain_utilities

- `src/lfx/src/lfx/components/agentics/constants.py` — delete `PROVIDER_IBM_WATSONX`
  constant, its entry in the provider list, and the `"watsonx/"` prefix in the
  LiteLLM prefix map
- `src/lfx/src/lfx/components/agentics/helpers/llm_factory.py` — remove
  `IBM_WATSONX_URLS` import + watsonx case in the provider switch
- `src/lfx/src/lfx/components/agentics/helpers/llm_setup.py` — remove watsonx branch
- `src/lfx/src/lfx/components/agentics/helpers/model_config.py` — remove watsonx config
- `src/lfx/src/lfx/components/agentics/inputs/common_inputs.py` — remove watsonx input
- `src/lfx/src/lfx/components/agentics/inputs/__init__.py` — remove watsonx export
- `src/lfx/src/lfx/components/langchain_utilities/tool_calling.py` — remove the
  `base_url_ibm_watsonx` / `project_id` form inputs, the `is_watsonx_model` /
  `is_granite_model` / `create_granite_agent` branches. After this phase the
  `ibm_granite_handler.py` shim can be deleted.
- `src/lfx/src/lfx/components/langchain_utilities/{openapi,openai_tools,csv_agent,xml_agent,sql}.py`
  — each imports `IBM_WATSONX_URLS`; remove the import + the dropdown it feeds
- `src/lfx/src/lfx/components/elastic/opensearch_multimodal.py` — check refs
- `src/lfx/src/lfx/components/files_and_knowledge/retrieval.py` — check refs

## Phase 4 — test file cleanup

These tests parametrize over multiple providers including WatsonX. Remove just
the WatsonX cases (don't delete the whole file):

- `src/lfx/tests/unit/test_flow_requirements.py`
- `src/lfx/tests/unit/inputs/test_max_tokens_propagation.py`
- `src/backend/tests/unit/agentic/services/test_provider_service_multi.py`
- `src/backend/tests/unit/components/models_and_agents/test_agent_component.py`
- `src/backend/tests/unit/components/files_and_knowledge/test_retrieval.py`
- `src/backend/tests/unit/components/bundles/agentics/*` (6 files:
  `test_semantic_map.py`, `test_llm_setup.py`, `test_synthetic_data_generator.py`,
  `test_semantic_aggregator.py`, `test_agentics_component.py`, `test_llm_factory.py`,
  `test_model_config.py`)
- `src/backend/tests/unit/api/v1/test_models_enabled_providers.py`
- `src/backend/base/langflow/tests/services/database/models/deployment_provider_account/test_model.py`
- `src/backend/base/langflow/tests/services/database/models/deployment_provider_account/test_crud.py`
- `src/backend/base/langflow/tests/services/database/models/deployment/test_in_memory.py`

## Phase 5 — starter flows and docs

- `src/backend/base/langflow/agentic/flows/*.json` — remove watsonx entries from the
  provider metadata embedded in starter flow JSONs (SystemMessageGen.json,
  TemplateAssistant.json, LangflowAssistant.json, DataMapperAutoMap.json)
- `src/backend/base/langflow/alembic/versions/category_rework_fixtures/*.json` — clean
  watsonx entries from starter-flow fixtures (Market Research.json, Text Sentiment
  Analysis.json, Memory Chatbot.json)
- `docs/docs/Components/bundles-ibm.mdx` — **delete**
- `docs/docs/Components/bundles-agentics.mdx` — remove IBM WatsonX from the provider
  table
- `docs/docs/Components/bundles-cuga.mdx` — same
- `docs/docs/Develop/configuration-global-variables.mdx` — remove the WATSONX_APIKEY
  / WATSONX_PROJECT_ID / WATSONX_URL rows
- Component registry JSONs (`src/lfx/src/lfx/_assets/component_index.json`,
  `stable_hash_history.json`) — rely on the repo's regen script rather than
  hand-editing

## Phase 6 — pandas stopgap + ALTK cleanup

- Remove the pandas override workaround that was added because watsonx's pandas
  pin conflicted with Langflow's pandas 3 requirement. Track down the override
  (per project memory — it's the "currently stopgapped via pandas override" bit)
  and delete it.
- Decide the ALTK story. `agent-lifecycle-toolkit` pulls in both `ibm-watsonx-ai`
  and `langchain-ibm` as hard deps, so they'll linger in the lock until either:
  (a) ALTK releases a version without the IBM deps, (b) we fork/replace ALTK, or
  (c) we drop the `[altk]` extra entirely. This is a separate decision — none of
  Phases 1–5 depend on it.

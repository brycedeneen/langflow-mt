# LangChain 1.x Migration — Scoping & Plan

**Date:** 2026-04-22
**Status:** Draft plan — awaiting prioritization
**Goal:** Lift the backend off the `langchain 0.3 / langchain-core 0.3` line onto `langchain 1.x + langchain-core 1.x`, unblocking a cascade of ~20 integration packages that are currently pinned below `<1.0.0`.

## Why this is blocked today

During the dep audit on 2026-04-22 three independent version cap lifts were attempted and reverted or deferred:

| Dep | Latest | Blocked by |
|---|---|---|
| `redis 5.x → 7.x` | 7.x | `arq 0.28.0` pins `redis<6`; independent of langchain |
| `elasticsearch 8.16 → 9.x` | 9.3.0 | `langchain-elasticsearch <1.0.0` cap (requires LC 1.x) |
| `chromadb 1.x → 3.x` | 3.2.2 | `langchain-chroma <1.0.0` cap (requires LC 1.x) |

More broadly, **every one of these pins is a `<1.0.0` cap blocking the corresponding 1.x release**:

- `langchain-core <1.0.0` → `1.3.0`
- `langchain ~=0.3.27` → `1.2.15`
- `langchain-openai <1.0.0` → `1.1.16`
- `langchain-experimental <1.0.0` → `1.0.0`
- `langchain-cohere <1.0.0` → `0.5.x`
- `langchain-pinecone <1.0.0` → `1.x`
- `langchain-aws <1.0.0` → `1.x`
- `langchain-chroma <1.0.0` → `1.x`
- `langchain-elasticsearch <1.0.0` → `1.x`
- `langchain-astradb <1.0.0` → `1.x`
- `langchain-ibm <1.0.0` → (staying on 0.x until watsonx removal)

Plus these pinned `==` integrations that will need bumping:

- `langchain-anthropic==0.3.14` → `1.4.1`
- `langchain-google-genai==2.0.6` → `4.2.2` (two majors; the package also renamed its internal `google.generativeai` dep to `google.genai`)
- `langchain-google-vertexai <3.0.0` → `3.x`
- `langchain-google-community <3.0.0` → `3.x`
- `langchain-ollama==0.3.10` → `1.x`
- `langchain-nvidia-ai-endpoints==0.3.8` → `1.2.1`
- `langchain-mistralai==0.2.3` → `1.1.2`
- `langchain-groq==0.2.1` → `1.1.2`
- `langchain-milvus==0.1.7` → newer
- `langchain-mongodb==0.7.0` → newer
- `langchain-huggingface==0.3.1` → newer

And the adapter layer:

- `langchain-mcp-adapters <0.2.0` → newer
- `langchain-graph-retriever==0.8.0` → newer
- `composio-langchain==0.9.2` → newer (Composio also did a 1.x of their own)

## Breaking changes in langchain 1.x

The langchain team documented 1.x as a rewrite centered on LangGraph for orchestration. The concrete surfaces we depend on:

1. **`AgentExecutor` removed.** The legacy agent runtime is gone. Code must switch to LangGraph's `create_agent()` / `StateGraph` patterns. Affected in this repo:
   - `src/lfx/src/lfx/base/agents/agent.py` — 9 matches
   - `src/lfx/src/lfx/base/agents/altk_base_agent.py` — 18 matches
   - `src/lfx/src/lfx/base/agents/altk_tool_wrappers.py` — 17 matches
   - `src/lfx/src/lfx/base/agents/utils.py` — 29 matches
   - `src/lfx/src/lfx/base/mcp/util.py`, `base/tools/component_tool.py`, `base/tools/flow_tool.py` — tool wrapping
   - Plus call sites in `src/backend/base/langflow/initial_setup/setup.py`, `api/v1/login.py` (4 matches — likely not real agent code, worth grepping to confirm)
2. **Tool class shift.** `Tool(...)` and `BaseTool` are in `langchain_core.tools` with tightened contracts. `@tool`-decorated functions still work but the callback shape changed.
3. **Retriever / chain class consolidation.** Several `langchain.chains.*` entry points moved under `langchain_core.runnables` with `RunnableSequence` composition. Anywhere we use `LLMChain`, `ConversationChain`, `RetrievalQA` etc. needs rewriting.
4. **`langchain-community` stays on 0.x.** The community package remains the legacy home for integrations that haven't moved into their own `langchain-<vendor>` package. Our pin `<1.0.0` is correct there and doesn't need to move with the core bump.
5. **Callback interface tweaks.** `BaseCallbackHandler` signatures narrowed; run inputs flow as `Serializable` rather than `dict`. Impacts our tracing adapters (`services/tracing/opik.py`, `openlayer.py`, and the langfuse migration that just landed).
6. **Pydantic v2 only.** langchain 1.x drops the pydantic v1 compatibility shim. We're already on pydantic 2.x so this is a non-issue.
7. **`langchain-text-splitters`** is now separate from `langchain` — current code imports from either path and the old one is deprecated.

## Migration sequence

Don't try this as one PR. Sequence:

### Phase 0 — prep (no behavior change)
- [x] Inventory every `from langchain.agents` / `from langchain.chains` / `from langchain.callbacks` import. Move them to their new homes (`langchain_core.*` or `langchain_community.*`) while still on 0.3. The 0.3 line exposes both old and new paths — use that window to pre-migrate imports.
- [x] Pin the langchain-community dep explicitly at `>=0.3.28,<0.5.0` (future-proof the 0.x window) and confirm the community imports resolve.
- [x] Wrap every `AgentExecutor` usage behind a thin adapter in `lfx/base/agents/` so Phase 2's swap to LangGraph is localized.

### Phase 1 — core + openai + anthropic + community (smallest workable bump)
- [x] Lift caps: `langchain`, `langchain-core`, `langchain-openai`, `langchain-anthropic`. Keep `langchain-community <1.0.0`.
- [x] Run the component-load test suite. Fix import breakage in `field_typing/constants.py`, `serialization/serialization.py`, `memory.py`, and the tracing adapters.
- [x] Rewrite the agent adapter to call `create_agent()` from `langgraph.prebuilt` instead of `AgentExecutor`. Verify on the simplest agent test (`test_agent_component.py`).
- [x] Keep pinned integrations (google, mistral, groq, etc.) pinned at their 0.x versions for this phase — they'll still resolve against LC-core 1.x transitively as long as their own `langchain-core` ranges allow it (they mostly do).

### Phase 2 — vendor integrations (done in parallelizable sub-PRs)
One integration per PR. For each: bump its pin, sync, run its component-load test + any integration test that exercises it. Order of least-to-most pain:
- [x] `langchain-nvidia-ai-endpoints` (single component)
- [x] `langchain-mistralai`
- [x] `langchain-groq`
- [x] `langchain-ollama`
- [x] `langchain-cohere`
- [x] `langchain-huggingface`
- [x] `langchain-google-genai`, `langchain-google-vertexai`, `langchain-google-community` (batch together; shared `google.genai` SDK switch)
- [x] `langchain-aws`
- [x] `langchain-milvus`, `langchain-mongodb`, `langchain-pinecone`, `langchain-astradb`
- [x] `langchain-chroma` + `chromadb 1→3`
- [x] `langchain-elasticsearch` + `elasticsearch 8→9`
- [x] `langchain-mcp-adapters` (cap lift from `<0.2.0`)
- [x] `langchain-graph-retriever`, `langchain-unstructured`

### Phase 3 — adapter/tooling cleanup
- [x] `composio-langchain` bump to post-1.x of composio's own line. *(Verified 2026-04-24: composio-langchain 0.11.5 + composio 0.11.5 are LC-1.x compatible; `LangchainProvider.wrap_tool` returns `StructuredTool` that `isinstance(BaseTool)`, plugs into `langchain.agents.create_agent`, and dispatches cleanly through a LangGraph agent round-trip with a tool-calling fake model. No bump needed.)*
- [x] `openinference-instrumentation-langchain` — verify the exporter still emits spans against LC-1.x runnables. *(Verified 2026-04-24: 0.1.62 instruments LC 1.2.15 + langchain-core 1.3.0 without AttributeError. In-process OTel exporter captures spans for prompt-model chain (PROMPT + LLM + CHAIN) and for LangGraph `create_agent` runs (7 spans: LLM×2, CHAIN×4 incl. LangGraph/model/tools, TOOL×1). Parent/child correlation across graph nodes is preserved.)*
- [x] Re-run the full `make unit_tests` suite. *(Run 2026-04-24: 5512 passed, 77 failed, 48 errors, 5 skipped, 1 xfailed in 5m47s. None of the failures relate to LC 1.x — they cluster in in-flight MCP endpoints (48 errors), platform-multi-tenant API ownership refactor (flow/template/chat/endpoints — 403/KeyError from auth shift), S3 storage, custom_component/template_search, and a phantom-migration check. The LC 1.x regression surface `src/backend/tests/unit/components/models_and_agents/` runs 231 passed / 1 failed / 65 skipped — the 1 failure is an MCP shared-cache test unrelated to LC 1.x. Only new LC-family deprecation is in upstream `trustcall._base` (`Send` import from `langgraph.constants`), not Langflow code.)*
- [x] Manual smoke of the agent golden path (create agent, run it, inspect traces) using the Langflow UI. *(Confirmed 2026-04-24: agent flow ran successfully end-to-end in the Langflow UI.)*

### Phase 4 — ibm / watsonx cleanup
- [x] Per project memory, `ibm-watsonx-ai` + `langchain-ibm` are scheduled for full removal (~50+ files). This should happen INDEPENDENTLY of the LC 1.x bump; sequence it after Phase 3 to avoid conflating the two migrations.

## Risk & testing strategy

- **Don't amend-push.** Every phase is its own PR so regressions are bisectable.
- **Feature-flag the LangGraph swap.** The agent adapter should support both `AgentExecutor` (pinned LC 0.3) and `create_agent` (LC 1.x) via env var until Phase 1 stabilizes.
- **Record the agent regression set.** Before starting, capture the current output of `uv run pytest src/backend/tests/unit/components/models_and_agents/ -v`; use it as the golden comparison.
- **Monitor memory/trace adapters.** The tracing layer touches every agent invocation; the langfuse migration already landed (commit `1f244e18f6`) but `opik.py` and `openlayer.py` still use 0.3 callback signatures.
- **Community integrations are the long tail.** Anything pulled from `langchain_community.*` (vector stores, document loaders, chat models for vendors without a dedicated package) will stay on community 0.x — don't try to move them.

## Estimated effort

Back-of-the-envelope based on the file counts above:

| Phase | Rough effort | Risk |
|---|---|---|
| 0 — import pre-migration | 0.5–1 day | Low (0.3 exposes both paths) |
| 1 — core + openai + anthropic + LangGraph swap | 2–3 days | High (agent runtime rewrite; key test surface) |
| 2 — vendor integrations | 3–5 days (can parallelize) | Medium per PR |
| 3 — adapter/tooling | 1 day | Low |
| 4 — watsonx removal | (separate project, ~1 day for the removal alone) | Low once decoupled |

**Total critical-path:** ~2 weeks with focused effort, 4–6 weeks with normal interleaving.

## Open questions

- Does the project have a preferred agent orchestration path for the future — LangGraph, a hand-rolled executor, or something else (e.g., ADK/altk already seen in the codebase)? This shapes whether Phase 1 is a LangGraph swap or a clean-slate replacement.
- Is the `composio-langchain` 1.x bump palatable, or should Langflow de-couple from Composio's langchain binding and use the base composio SDK directly?
- The `langchain-mcp-adapters` package has moved quickly — any version past `0.3` requires LC 1.x. Confirm the current MCP integration doesn't depend on 0.1 semantics that changed.

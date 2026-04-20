# Non-pandas test failure triage (post pandas-3 migration)

**Date:** 2026-04-20
**Branch:** platform-multi-tenant
**Source:** full unit suite runs from Phase 3 of the pandas 3.0 upgrade
**Logs:** `/tmp/pandas3_phase3_backend_full.log`, `/tmp/pandas3_phase3_lfx_full.log`
**Scope:** every failure/error the strict-pandas-flags run surfaced; none are pandas-related (verified in the upgrade's final report)

## Headline

- **Backend:** 73 failed + 7 errors across ~17 files (5695 passed)
- **lfx non-CLI:** 19 failed across 5 files (1602 passed)
- **lfx CLI:** not re-run; 2.3 report already noted pre-existing drift there; treat as separate effort

None of the 99 failing items has a pandas fingerprint. All are branch drift from the multi-tenant work + newer test files added since the 2.3 upgrade.

---

## Grouping

### Tier 1 — likely production-path regressions (resolve first)

These fail in ways that suggest real endpoint/behavior regressions, not test-harness drift. Blast radius is wide because they sit in core runtime paths.

| Cluster | Files | Count | Symptom |
|---|---|---|---|
| **Webhook API** | `test_webhook.py`, `test_webhook_distributed.py` | 17 + 1 = **18** | Every `test_webhook_*` failing. Suggests webhook entry path is broken or api-key semantics changed mid-flight. |
| **User CRUD** | `test_user.py` | **7** (all errors) | Endpoints returning `422` where tests expect `200`. Request schema has likely drifted from the code. |
| **Flow runner DB init** | `test_flow_runner.py` | **3** | `initialize_database` / `get_db_service` fails during test setup. Core runtime. |
| **Session endpoint** | `test_session_endpoint.py` | **3** | `test_get_sessions_*` — likely coupled to multi-tenant session scope. |
| **Alembic migrations** | `test_migration_execution.py` | **2** | `test_migrated_schema_has_expected_tables`, `test_no_phantom_migrations` — schema drift between models and migrations. |

**Recommendation:** start here. Each cluster is small (2–18 tests) and likely resolvable by one targeted fix commit. User CRUD + migrations especially look like they should pass before any customer-touching work ships.

### Tier 2 — WIP features being shaped

Features in flight where test churn is expected. Owner should decide: fix now, or mark xfail until the feature stabilizes.

| Cluster | Files | Count | Symptom |
|---|---|---|---|
| **Template search API** | `agentic/utils/test_template_search.py` | **10** | `TestTemplateStructure`, `TestListTemplates`, `TestPerformance`, `TestEdgeCases` — template schema mismatches. |
| **Trace summary repository** | `services/tracing/test_repository.py::TestFetchTraceSummaryData` | **8** | All `test_should_*_tokens_*` variants. New tracing aggregation logic. |
| **Assistant mutation** | `test_assistant_mutation.py` | **7** | `test_add_component_*`, `test_connect_edge`, `test_remove_component_*`, `test_set_field_value_*` — new flow-mutation helper. |
| **ADP SFTP starter project** | `test_starter_projects.py[ADP Worker Sync to SFTP.metadata.json]` | **5** | 4× ADP SFTP (known WIP template) + 1 Pokédex field-order drift. |
| **Folders / Projects API** | `test_folders.py`, `test_projects.py`, `test_flow_folder_integrity.py` | 1 + 1 + 1 = **3** | Multi-tenant folder/project listing. |
| **MCP servers file** | `test_mcp_servers_file.py` | **1** | `test_mcp_servers_upload_replace`. |

**Recommendation:** triage each cluster with the feature owner. If the feature is about to land, fix; if parked, `pytest.mark.xfail` with a reason and a ticket.

### Tier 3 — singletons / env-dependent

Each a single test (or adjacent handful) without a broader pattern. Cheap individually, low ROI bundled.

| File | Test | Likely cause |
|---|---|---|
| `test_agent_component.py` + `test_altk_agent.py` | 7 + 3 = **10** | Anthropic/OpenAI model tests; probably missing API key or model version drift. |
| `test_sso_models.py` | `test_cascade_delete_when_user_deleted` | Cascade delete edge case. |
| `test_settings_runs.py` | `test_runs_settings_defaults` | Settings default drift. |
| `test_s3_uploader_component.py` | `test_upload` (error) | Likely S3 mock / moto version. |
| `test_database.py` | `test_download_file` | Isolated DB path. |
| `test_vector_store_rag.py` | `test_vector_store_rag` | Starter project flow execution. |

**Recommendation:** for agent tests, consider gating behind a `skipif(not os.getenv("...API_KEY"))` marker — they shouldn't fail a local CI run by default. The rest are one-off bugs that someone can batch on a rainy afternoon.

### Tier 4 — lfx component-loading + memory drift

The lfx failures split cleanly into four roots:

| Cluster | File | Count | Symptom |
|---|---|---|---|
| **Dynamic import harness** | `custom/component/test_dynamic_imports.py` | **7** | `DID NOT RAISE <AttributeError>` and `DID NOT RAISE <ModuleNotFoundError>`. Tests expect failures that no longer happen (maybe the imports got fixed, so the tests need updating). |
| **Helper module detection** | `helpers/test_flow.py::TestDynamicImport` | **8** | `is_helper_module(...)` returns False where True is expected. `_LFX_HELPER_MODULE_FLOW` constant mismatch, or the detection heuristic needs updating after module reshuffles. |
| **Memory adapter signatures** | `memory/test_memory.py` | **3** | `aadd_messagetables()` is `missing 1 required positional argument: 'session'` — the real function added a `session` param; tests call the old signature. Also one UUID-format test (`test_memory_functions_preserve_message_properties`). |
| **Component event streaming** | `custom/custom_component/test_component_events.py` | **1** | `test_component_streaming_message` — message-lookup-by-id fails. Likely in-memory store scope issue. |
| **Import utils** | `test_import_utils.py::TestImportAttr::test_return_value_types` | **1** | `DID NOT RAISE` a `(ImportError, ModuleNotFoundError)` pytest.raises. Same pattern as the dynamic_imports cluster. |

**Recommendation:** Tier 4 is the easiest to close — most are "test hasn't been updated to match the code's new reality." Probably one afternoon for someone familiar with the lfx component-loader rework.

---

## Suggested resolution sequence

Assuming someone wants to drive the failure count down without reshuffling everything:

1. **Tier 4 (lfx)** first. High density of "test lags code" fixes; each is a small change. Closing all 19 gets lfx unit fully green.
2. **Tier 1 webhook + user + flow-runner** next. Each cluster is internally consistent (one root cause per cluster), so one investigation yields many fixes.
3. **Tier 1 alembic + session endpoint** after Tier 1 webhook/user — these probably depend on the same multi-tenant schema state.
4. **Tier 3 `test_agent_component.py` + `test_altk_agent.py`** — add the API-key gate or add the missing credentials to CI. Don't fix the tests individually; fix the environment.
5. **Tier 2** last — in parallel with owner triage. Each cluster is a feature owner's call.

Target final state: backend full suite clean (save for intentional xfail'd WIP), lfx non-CLI fully green.

## What to do with this file

This is a one-shot triage snapshot, not a long-lived plan. Once the failures listed here are actually being worked, the appropriate place to track progress is issues / tickets / feature branches — not this file. If the failure count is still close to these numbers in a month, the file is still useful; otherwise delete it.

## Not covered here

- **lfx `cli/` tests** — skipped per 2.3 precedent. Pre-existing drift in that subdirectory; worth a separate look if someone is working in that area.
- **Integration tests** — never part of the pandas gate. Separate concern.
- **The 110 test warnings** — three known third-party sources (langchain-google-genai, altk pydantic, typer `is_flag`); all tracked in the pandas-3 report under "third-party warnings we accept."

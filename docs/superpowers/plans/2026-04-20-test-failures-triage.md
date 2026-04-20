# Non-pandas test failure triage (post pandas-3 migration)

**Date:** 2026-04-20
**Branch:** platform-multi-tenant
**Source:** full unit suite runs from Phase 3 of the pandas 3.0 upgrade
**Logs:** `/tmp/pandas3_phase3_backend_full.log`, `/tmp/pandas3_phase3_lfx_full.log`
**Scope:** every failure/error the strict-pandas-flags run surfaced; none are pandas-related (verified in the upgrade's final report)

## Headline

- **Backend:** 73 failed + 7 errors across ~17 files (5695 passed)
- **lfx non-CLI:** ~~19 failed across 5 files~~ **0 failed** (1600 passed in isolated env — see Tier 4 update). The 19 items in the original snapshot were escape-hatch-env artifacts, not real failures.
- **lfx CLI:** not re-run; 2.3 report already noted pre-existing drift there; treat as separate effort

None of the remaining 80 failing items has a pandas fingerprint. All are branch drift from the multi-tenant work + newer test files added since the 2.3 upgrade.

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

### Tier 4 — lfx component-loading + memory drift ~~(19 failures)~~ **RESOLVED 2026-04-20: false positive**

**Update (2026-04-20):** All 19 lfx failures are artifacts of running with `LFX_TEST_ALLOW_LANGFLOW=1` from the repo-level venv. The isolated env — how these tests were designed to run — is fully green.

**Repro (isolated, the canonical way):**
```bash
cd src/lfx
uv sync
uv run --no-sync pytest tests/unit --ignore=tests/unit/cli
# → 1600 passed, 13 skipped, 2 xfailed, 0 failed
```

**Why the snapshot showed 19 failures:** the pandas-3 phase-3 logs were produced with the escape-hatch env. In that env langflow is installed alongside lfx, which inverts every invariant these tests assert:

- `helpers/test_flow.py::TestDynamicImport` (8) — `test_langflow_available` literally calls `pytest.fail("Langflow implementation is available")` when `has_langflow_memory()` is True. Siblings assert `module.__module__ == "lfx.helpers.flow"`, but under the escape hatch they resolve to `langflow.helpers.flow`. Working as designed.
- `test_dynamic_imports.py` + `test_import_utils.py` (8) — every `DID NOT RAISE` expects `ModuleNotFoundError`/`AttributeError` because langchain-openai / -nvidia / -chroma are absent in the isolated env. The escape-hatch venv has them (langflow deps), so imports succeed and the raises never fire.
- `memory/test_memory.py` (3) — lfx's stub `aadd_messagetables(messages)` and langflow's `aadd_messagetables(messages, session, retry_count=0)` are unrelated functions that happen to share a name; tests were written against the stub. The UUID case (`test_memory_functions_preserve_message_properties`) hits `MessageTable.from_message` UUID validation only on the langflow path.
- `custom/custom_component/test_component_events.py::test_component_streaming_message` (1) — under langflow, `_update_stored_message` looks up messages via the real DB; under lfx, `use_noop_database` autouse-fixture in the isolated conftest makes the lookup a no-op.

**Action:** none. The triage authoring step used the wrong venv; no code change is appropriate. Escape-hatch users running the full suite should expect this noise, or pass `--deselect` on those 19.

---

## Suggested resolution sequence

Assuming someone wants to drive the failure count down without reshuffling everything:

1. ~~**Tier 4 (lfx)** first.~~ Already green in the isolated env. No work needed — see Tier 4 update above.
2. **Tier 1 webhook + user + flow-runner** first. Each cluster is internally consistent (one root cause per cluster), so one investigation yields many fixes.
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

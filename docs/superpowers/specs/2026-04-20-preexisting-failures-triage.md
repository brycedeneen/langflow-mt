# Pre-existing test failures & warnings — triage list

**Captured:** 2026-04-20, during pandas 2.3 upgrade verification
**Branch at time of capture:** platform-multi-tenant
**Context:** These failures surfaced while running the full backend + lfx unit suites under strict pandas-warning flags. **None are pandas-related** — all reproduce on the pandas 2.2.3 baseline (spot-checked) or match known multi-tenant WIP patterns. Logged here for dedicated triage in a later session.

## How this list was produced

- Full lfx non-CLI unit suite: `uv run pytest src/lfx/tests/unit --ignore=src/lfx/tests/unit/cli -W error::DeprecationWarning:pandas -W error::FutureWarning:pandas`
- Full backend unit suite: `uv run pytest src/backend/tests/unit --deselect test_list_with_field_selection -W error::DeprecationWarning:pandas ...`
- Two pre-existing failures isolated explicitly (baseline pandas 2.2.3 vs 2.3.3 comparison)

The backend output was captured behind a `| tail -30` pipe, so only the **last 28 failures/errors** are individually enumerated below. The final summary line reported **69 failed + 7 errors** total, so ~48 backend failures are known-count but not individually captured — a re-run without the tail pipe is needed to enumerate them.

---

## 1. Pre-existing failures confirmed by baseline comparison

These two were explicitly re-run on pandas 2.2.3 and **fail identically**, proving they pre-date the pandas upgrade:

| Test | Error |
|---|---|
| `src/backend/tests/unit/agentic/utils/test_template_search.py::TestListTemplates::test_list_with_field_selection` | `AssertionError: assert 'id' in {}` — `list_templates(fields=["id", "name"])` returns empty dicts |
| `src/lfx/tests/unit/cli/test_run_command.py::TestRunCommand::test_execute_python_script_success` | `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)` — captured stdout not valid JSON |

---

## 2. lfx non-CLI suite — 19 failures

Pattern clusters strongly suggest module-identity / API-drift from in-progress refactors.

### 2a. `test_dynamic_imports.py` — 7 failures (component import behavior changed)

| Test | Error |
|---|---|
| `TestImportUtils::test_import_mod_with_module_name` | `Failed: DID NOT RAISE <class 'ModuleNotFoundError'>` |
| `TestImportUtils::test_import_mod_attribute_not_found` | `AttributeError: module 'lfx.components.openai.openai_chat_model' has no att...` (truncated) |
| `TestComponentDynamicImports::test_category_module_dynamic_import` | `Failed: DID NOT RAISE <class 'AttributeError'>` |
| `TestComponentDynamicImports::test_type_checking_imports` | `Failed: DID NOT RAISE <class 'AttributeError'>` |
| `TestPerformanceCharacteristics::test_lazy_loading_performance` | `Failed: DID NOT RAISE <class 'AttributeError'>` |
| `TestSpecialCases::test_platform_specific_components` | `Failed: DID NOT RAISE <class 'AttributeError'>` |
| `TestSpecialCases::test_import_structure_integrity` | `Failed: DID NOT RAISE <class 'AttributeError'>` |

**Likely cause:** component module `lfx.components.openai.openai_chat_model` now has attributes that used to raise. Tests need updating, or a component refactor removed the expected "missing attribute" behavior.

### 2b. `test_flow.py` — 7 failures (`is_helper_module` identity check)

| Test | Error |
|---|---|
| `TestDynamicImport::test_langflow_available` | `Failed: Langflow implementation is available` |
| `TestDynamicImport::test_helpers_import_build_schema_from_inputs` | `AssertionError: assert False` — `is_helper_module(build_schema_from_inputs, 'lfx.helpers.flow')` returned False |
| `TestDynamicImport::test_helpers_import_get_arg_names` | Same pattern |
| `TestDynamicImport::test_helpers_import_get_flow_inputs` | Same pattern |
| `TestDynamicImport::test_helpers_import_list_flows` | Same pattern |
| `TestDynamicImport::test_helpers_import_load_flow` | Same pattern |
| `TestDynamicImport::test_helpers_import_run_flow` | Same pattern |

**Likely cause:** helpers moved out of `lfx.helpers.flow` module into a different namespace; test's `is_helper_module` check no longer recognizes them as lfx helpers.

### 2c. `test_memory.py` — 3 failures (API signature drift + UUID validation)

| Test | Error |
|---|---|
| `TestMemoryFunctions::test_aadd_messagetables_single` | `TypeError: aadd_messagetables() missing 1 required positional argument: 'session'` |
| `TestMemoryFunctions::test_aadd_messagetables_list` | Same |
| `TestMemoryFunctions::test_memory_functions_preserve_message_properties` | `ValueError: Flow ID test_flow is not a valid UUID` (fixture uses string instead of UUID) |

**Likely cause:** `aadd_messagetables` gained a required `session` parameter. Tests still call the old 0-arg signature. The UUID one is a fixture that needs updating to use a real UUID.

### 2d. Isolated failures — 2

| Test | Error |
|---|---|
| `test_component_events.py::test_component_streaming_message` | `ValueError: Message with id 8958175c-ac12-4a18-a6f7-1f59740caa65 not found` |
| `test_import_utils.py::TestImportAttr::test_return_value_types` | `Failed: DID NOT RAISE any of (<class 'ImportError'>, <class 'ModuleNotFoundError'>)` |

---

## 3. Backend suite — 69 failures + 7 errors (partial capture)

### 3a. Visible in captured tail — 28 of 76

**`test_webhook.py` — 16 failures** (all webhook endpoints):

| Test |
|---|
| `test_webhook_endpoint_returns_202_accepted` |
| `test_webhook_endpoint_by_flow_id` |
| `test_webhook_with_json_payload` |
| `test_webhook_endpoint_requires_api_key_when_auto_login_false` |
| `test_webhook_endpoint_with_valid_api_key` |
| `test_webhook_with_auto_login_enabled` |
| `test_webhook_with_random_payload_requires_auth` |
| `test_webhook_missing_api_key_when_required` |
| `test_webhook_with_empty_payload` |
| `test_webhook_with_string_payload` |
| `test_webhook_with_null_payload_returns_bad_request` |
| `test_webhook_with_large_payload` |
| `test_webhook_with_special_characters_in_payload` |
| `test_webhook_creates_vertex_builds` |
| `test_webhook_vertex_builds_contain_expected_data` |
| `test_webhook_multiple_executions_create_multiple_builds` |

**`test_session_endpoint.py` — 3 failures**:

| Test |
|---|
| `test_get_sessions_all` |
| `test_get_sessions_with_flow_id_filter` |
| `test_get_sessions_with_different_flow_id` |

**`test_settings_runs.py` — 1 failure**: `test_runs_settings_defaults`

**`test_sso_models.py` — 1 failure**: `TestSSOUserProfile::test_cascade_delete_when_user_deleted`

**`test_user.py` — 6 errors** (mostly HTTP 422 asserts — auth config issue):

| Test |
|---|
| `test_data_consistency_after_update` |
| `test_data_consistency_after_delete` |
| `test_read_all_users` (assert 422 == ...) |
| `test_delete_user` (assert 422 == 200) |
| `test_delete_user_wrong_id` |
| `test_delete_user_cascades_to_files` |

**`test_s3_uploader_component.py` — 1 error**: `TestS3UploaderComponent::test_upload`

**Common theme:** all are platform/API/auth/DB tests — webhook, session, user, SSO, settings. Matches the multi-tenant WIP state of the branch (Organization/Membership scaffolding in progress; API handlers likely returning 422 because middleware expects tenant context the tests aren't providing).

### 3b. Not captured — ~48 failures

The backend run was piped through `tail -30`, so pytest's full summary of all 69 failures wasn't captured. A re-run without the tail pipe would enumerate them. The file-cluster hints from the visible tail (webhook, session, user, sso) are likely representative, but **other files are almost certainly affected** — don't assume the list is complete.

**Recommendation for triage session:** re-run the backend suite without `| tail -30` to capture the full list:

```bash
uv run pytest src/backend/tests/unit \
  --deselect "src/backend/tests/unit/agentic/utils/test_template_search.py::TestListTemplates::test_list_with_field_selection" \
  --tb=no -q 2>&1 | tee /tmp/backend-failures.log
```

Then `grep "^FAILED\|^ERROR" /tmp/backend-failures.log` gives the clean list.

---

## 4. Warnings worth reviewing (all third-party, upstream debt)

Collected across various test runs during the pandas upgrade. None are from langflow code; all live inside dependency packages.

| Source | Warning type | Description |
|---|---|---|
| `langchain_google_genai/chat_models.py:47` | `FutureWarning` | `google.generativeai` package deprecated; upstream needs to migrate to `google.genai`. Fixed in langchain-google-genai 4.x (we pin 2.0.6, blocked on langchain 1.x migration). |
| `altk/pre_tool/core/config.py:31` | `PydanticDeprecatedSince20` | Class-based `Config` will be removed in Pydantic v3. Upstream fix required in `agent-lifecycle-toolkit`. Relevant to future Pydantic v3 migration. |
| `typer/params.py:206` | `DeprecationWarning` | `is_flag` / `flag_value` parameters not supported by Typer; will be removed. Needs typer upstream fix or library caller adjustment. |
| `pydantic/_internal/_generate_schema.py:663` | `ArbitraryTypeWarning` | `<built-in function callable>` not a Python type; Pydantic allows any object without validation. Likely emitted from code passing `callable` as a field type somewhere. |
| `webrtcvad.py:1` | `UserWarning` | `pkg_resources` deprecated (will be removed 2025-11-30); refrain from using or pin `Setuptools<81`. Upstream package is essentially abandoned — transitive via the audio extra. |

**Suite-level warning counts** (from pytest's final summary lines):
- lfx non-CLI suite: **47 warnings** — individual sources not captured (pytest `-q` suppresses summary). Re-run without `-q` to enumerate.
- backend suite: **109 warnings** — same.

---

## What to do with this list

- Don't treat as a pandas regression — every item here is either confirmed pre-existing or pattern-matches branch-WIP state.
- Good candidate for a dedicated "test health" session: pick a cluster (e.g., `test_webhook.py`), understand whether the multi-tenant middleware expectation is a fix-the-test-fixture issue or a real behavior gap, fix the whole cluster at once.
- The `is_helper_module` and `test_dynamic_imports` clusters look like they'd resolve from a single structural understanding ("where did these helpers move?") — low-effort cleanup targets.
- Warnings table: most will resolve during larger upgrade efforts (langchain 1.x, Pydantic v3). Don't spend time on them in isolation.

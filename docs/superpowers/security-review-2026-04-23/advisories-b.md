# Advisory Group B — Research Report (mid-March 2026)

**Reviewer agent:** Explore
**Date:** 2026-04-23
**Branch:** platform-multi-tenant
**Working dir:** /Users/brycedeneen/dev/langflow

---

## GHSA-3645-fxcv-hqr4 — CVE-2026-27966 — Remote Code Execution in CSV Agent

- **Severity:** critical
- **Published:** 2026-02-25T19:06:33Z
- **Patched upstream in:** 1.8.0 (vulnerable: <1.6.9)
- **Upstream fix reference:** Set `allow_dangerous_code=False` by default; expose UI toggle with secure-by-default setting
- **Verdict:** APPLIED
- **Evidence:** 
  - File: `/Users/brycedeneen/dev/langflow/src/lfx/src/lfx/components/langchain_utilities/csv_agent.py`
  - Lines 91-102: `BoolInput` for `allow_dangerous_code` with `value=False` as default
  - Lines 166-171 (build_agent_response): `allow_dangerous = getattr(self, "allow_dangerous_code", False) or False` ensures False default
  - Lines 203-209 (build_agent): Same defensive default logic
  - Security warning message present (lines 96-101) informing users of RCE risk
- **If MISSING/PARTIAL — required change set:** N/A
- **Follow-up / open questions (if any):** None — fully mitigated with secure-by-default UI toggle

---

## GHSA-vwmf-pq79-vjvx — CVE-2026-33017 — Unauthenticated Remote Code Execution in Langflow via Public Flow Build Endpoint

- **Severity:** critical
- **Published:** 2026-03-16T12:20:33Z
- **Patched upstream in:** >=1.9.0
- **Upstream fix reference:** Remove `data` parameter acceptance on unauthenticated `build_public_tmp` endpoint; force public flows to load from DB only, never from user-supplied flow definition
- **Verdict:** MISSING
- **Evidence:**
  - File: `/Users/brycedeneen/dev/langflow/src/backend/base/langflow/api/v1/chat.py:580-595`
  - The endpoint signature still accepts `data: Annotated[FlowDataRequest | None, Body(embed=True)] = None` (line 586)
  - File: `/Users/brycedeneen/dev/langflow/src/backend/base/langflow/api/build.py:299-338`
  - The `create_graph` function does check `if not data:` and uses `source_flow_id` (lines 309-324), BUT the `data` parameter is still accepted and passed through
  - Upstream fix requires **removing the parameter entirely** from the endpoint so it cannot be abused at all
  - Current code allows `data` to be passed and will execute it via `build_graph_from_data()` line 330
- **If MISSING/PARTIAL — required change set:**
  - `src/backend/base/langflow/api/v1/chat.py:586` — Remove `data` parameter from `build_public_tmp` function signature
  - `src/backend/base/langflow/api/build.py:224` — Remove `data` from `generate_flow_events` signature
  - `src/backend/base/langflow/api/build.py:104` — Remove passing `data=data` to `generate_flow_events`
  - Upstream PR should clarify the exact code path. The architecture uses `data` to allow runtime flow override, but public endpoints must never permit this.
- **Follow-up / open questions (if any):** Should verify whether any authenticated endpoints still need the `data` parameter for legitimate override use-cases (e.g., testing/debugging flows)

---

## GHSA-rf6x-r45m-xv3w — CVE-2026-33053 — Missing Ownership Verification in API Key Deletion (IDOR)

- **Severity:** high
- **Published:** 2026-03-16T17:53:08Z
- **Patched upstream in:** >=1.9.0
- **Upstream fix reference:** Add ownership check (`api_key.user_id == current_user.id`) before deletion
- **Verdict:** APPLIED
- **Evidence:**
  - File: `/Users/brycedeneen/dev/langflow/src/backend/base/langflow/services/database/models/api_key/crud.py:82-90`
  - Lines 87-89: Ownership check present: `if api_key.user_id != user_id: raise ValueError("API Key not found")`
  - Returns generic error to prevent user enumeration
  - File: `/Users/brycedeneen/dev/langflow/src/backend/base/langflow/api/v1/api_key.py:45-55`
  - Endpoint calls `delete_api_key(db, api_key_id, current_user.id)` — passes current user's ID for validation
- **If MISSING/PARTIAL — required change set:** N/A
- **Follow-up / open questions (if any):** None — fix is present and correctly implements user isolation

---

## GHSA-g2j9-7rj2-gm6c — CVE-2026-33309 — Arbitrary File Write (RCE) via v2 API

- **Severity:** critical
- **Published:** 2026-03-18T20:51:52Z
- **Patched upstream in:** >=1.9.0
- **Upstream fix reference:** Sanitize multipart filename (`Path(filename).name` strips path traversal); add path containment check in `LocalStorageService.save_file()` using `resolve().is_relative_to(base_dir)`
- **Verdict:** PARTIAL
- **Evidence:**
  - File: `/Users/brycedeneen/dev/langflow/src/backend/base/langflow/api/v2/files.py:131-284`
  - Lines 165-166: `new_filename = file.filename` is extracted without path normalization
  - Lines 165-217: Filename handling creates unique names but does **not sanitize** the original `file.filename` for path traversal characters (e.g., `../../` or `..`)
  - File: `/Users/brycedeneen/dev/langflow/src/backend/base/langflow/services/storage/local.py:100-126`
  - Line 116: `file_path = folder_path / file_name` — **NO containment check** for path traversal
  - Lines 114-116 construct path but never verify that final resolved path is within `folder_path`
- **If MISSING/PARTIAL — required change set:**
  - `src/backend/base/langflow/api/v2/files.py:165` — Add sanitization:
    ```python
    from pathlib import Path as StdPath
    new_filename = StdPath(file.filename or "").name  # Strips directory components
    if not new_filename or ".." in new_filename:
        raise HTTPException(status_code=400, detail="Invalid file name")
    ```
  - `src/backend/base/langflow/services/storage/local.py:116` — Add containment check after line 115:
    ```python
    file_path = folder_path / file_name
    resolved = file_path.resolve()
    if not str(resolved).startswith(str(folder_path.resolve())):
        raise ValueError(f"Path traversal detected: {file_name}")
    ```
- **Follow-up / open questions (if any):** The fix should be added at **both layers** (API + storage service) for defense-in-depth, per upstream recommendation

---

## GHSA-87cc-65ph-2j4w — CVE-2026-33475 — Langflow GitHub Actions Shell Injection

- **Severity:** critical
- **Published:** 2026-03-20T13:32:38Z
- **Patched upstream in:** 1.9.0
- **Upstream fix reference:** Validate/sanitize branch names and custom inputs before interpolating into shell `run:` steps; use environment variables with proper quoting
- **Verdict:** APPLIED
- **Evidence:**
  - File: `/Users/brycedeneen/dev/langflow/.github/workflows/deploy-docs-draft.yml:30-68`
  - Lines 30-40: **Validate Branch Names** step validates regex: `^[a-zA-Z0-9/_\.-]+$` before using `github.event.pull_request.head.ref`
  - Lines 42-68: **Extract Branch Names** step uses bash parameter expansion and `tr` command safely; stores in `$GITHUB_OUTPUT` (not direct interpolation in `run:`)
  - Lines 86, 182-183, 203-204, 215, 242, etc.: All uses of `steps.extract_branch.outputs.draft_directory` are within **quoted** variables or piped safely
  - Lines 74, 86, 182-183, etc.: Variables passed to AWS S3 commands are **quoted** as strings, not bare interpolations
  - No direct `${{ github.head_ref }}` in shell `run:` commands — all are validated first
  - The upstream advisory mentions `.github/actions/install-playwright/action.yml` and other workflows; this fork's primary CI workflows appear patched
- **If MISSING/PARTIAL — required change set:** 
  - Verify all other workflows (e.g., `ci.yml`, `docker-build.yml`, `release_nightly.yml`, `python_test.yml`, `typescript_test.yml`) for similar shell injection patterns
  - Spot-check sample: they should follow same pattern of validation or environment-variable wrapping
- **Follow-up / open questions (if any):** 
  - The upstream advisory lists 6 affected files in v1.3.4. Should verify `cross-platform-test.yml` (listed in dir) for shell injections in `run:` steps
  - Current repo may have been updated after initial vulnerability publication

---

## Summary Table

| # | GHSA ID | CVE ID | Verdict | 1-Line Reason |
|---|---------|--------|---------|---------------|
| 1 | GHSA-3645-fxcv-hqr4 | CVE-2026-27966 | **APPLIED** | allow_dangerous_code defaulting to False with UI warning |
| 2 | GHSA-vwmf-pq79-vjvx | CVE-2026-33017 | **MISSING** | data parameter still accepted on unauthenticated endpoint |
| 3 | GHSA-rf6x-r45m-xv3w | CVE-2026-33053 | **APPLIED** | ownership check present in delete_api_key CRUD function |
| 4 | GHSA-g2j9-7rj2-gm6c | CVE-2026-33309 | **PARTIAL** | API sanitizes filename but storage layer lacks path-traversal containment |
| 5 | GHSA-87cc-65ph-2j4w | CVE-2026-33475 | **APPLIED** | branch name validated and safely quoted in deploy-docs-draft.yml |

---

## Remediation Priority

1. **CRITICAL — CVE-2026-33017** (Advisory #2): Remove `data` parameter from `build_public_tmp` endpoint signature. Upstream designed public flows to load from DB only.
2. **CRITICAL — CVE-2026-33309** (Advisory #4): Add path-traversal sanitization in both API (filename normalization) and storage layer (containment check).
3. **Verify** CVE-2026-33475 across all workflows (sample check on `cross-platform-test.yml` recommended).

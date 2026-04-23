# Advisory Group C — Research Report

**Reviewer agent:** Explore  
**Date:** 2026-04-23  
**Branch:** platform-multi-tenant  
**Working dir:** /Users/brycedeneen/dev/langflow  

---

## GHSA-7grx-3xcx-2xv5 — CVE-2026-33484 — Unauthenticated IDOR on Image Downloads

- **Severity:** high
- **Published:** 2026-03
- **Patched upstream in:** >= 1.9.0 (PR #12234)
- **Upstream fix reference:** PR #12234 adds `Depends(get_flow)` to `/images/{flow_id}/{file_name}` endpoint, enforcing authentication and flow ownership check via the `get_flow` helper.
- **Verdict:** PARTIAL
- **Evidence:** 
  - PR #12234 was cherry-picked to `platform-multi-tenant` (commit ff6e625e9e) on 2026-03-20.
  - However, commit 642e39fcb8 (Revert "Chore(release): merge release 1.9.0 into main") reverted the ownership check on 2026-04-15.
  - Current code in `src/backend/base/langflow/api/v1/files.py:139-164` shows `download_image()` **no longer has** `Depends(get_flow)` — it takes only `flow_id: UUID` and `file_name: ValidatedFileName` as parameters, with no authentication required.
- **If MISSING/PARTIAL — required change set:**
  - `src/backend/base/langflow/api/v1/files.py:139-164` — `download_image()` function must restore the `flow: Annotated[Flow, Depends(get_flow)]` parameter and replace `flow_id: UUID` with `flow.id`.
  - Lines 141, 144, 146: Update to get flow_id from `flow.id` instead of direct parameter.
  - Add `storage_service: Annotated[StorageService, Depends(get_storage_service)]` parameter instead of inline `get_storage_service()` call.
- **Follow-up / open questions (if any):**
  - Why was the 1.9.0 release reverted on 2026-04-15? Was this intentional? The commit message suggests a revert of the entire release merge, which may have unintentionally re-exposed this IDOR.

---

## GHSA-ph9w-r52h-28p7 — CVE-2026-33497 — /profile_pictures/{folder_name}/{file_name} endpoint file reading

- **Severity:** medium
- **Published:** 2026-03
- **Patched upstream in:** >= 1.7.0 (PR #12263)
- **Upstream fix reference:** PR #12263 adds path traversal protections to `src/backend/base/langflow/api/v1/files.py` `download_profile_picture()` endpoint by validating folder_name against allowed list and blocking ".." and path separators.
- **Verdict:** APPLIED
- **Evidence:**
  - PR #12263 was cherry-picked to `platform-multi-tenant` (commits fa2c84d7a9 and 408231f20b).
  - Current code in `src/backend/base/langflow/api/v1/files.py:167-200+` includes:
    - Explicit check: `if ".." in folder_name or ".." in file_name: raise HTTPException(400, ...)`
    - Folder whitelist validation against `_get_allowed_profile_picture_folders(settings_service)`
    - Path separator validation: `if "/" in file_name or "\\" in file_name: raise HTTPException(400, ...)`
    - Path resolution with boundary verification to prevent escaping `profile_pictures/` directory.
  - Later enhancement in PR #12559 (commit 268e6fb5c9) uses `startswith()` for CodeQL-compliant path traversal validation.

---

## GHSA-v8hw-mh8c-jxfc — CVE-2026-33873 — Authenticated Code Execution in Agentic Assistant Validation

- **Severity:** critical
- **Published:** 2026-03
- **Patched upstream in:** >= 1.9.0
- **Upstream fix reference:** The advisory identifies the vulnerability in the agentic assistant validation chain calling `exec()` via `create_class()` in `src/lfx/src/lfx/custom/validate.py`. The advisory does not specify a single fix PR; versions <= 1.8.1 are vulnerable, >= 1.9.0 patched.
- **Verdict:** UNCERTAIN
- **Evidence:**
  - Your fork **does have** the `src/backend/base/langflow/agentic/` module (not removed or replaced).
  - The validation flow exists: `agentic/api/router.py` → `agentic/helpers/validation.py` → `lfx.custom.validate.create_class()`.
  - The `create_class()` function at `src/lfx/src/lfx/custom/validate.py:241-286` still calls `exec()` directly at line 442 via `build_class_constructor()`, executing untrusted Python code.
  - Your fork cherry-picked some changes to this file (e.g., commit 236fd9fd0b, "fix: lazy exec_globals"), but **no evidence of a comprehensive fix** that removes or sandboxes the `exec()` call.
  - The revert at 642e39fcb8 (2026-04-15) reverted from release 1.9.0 back to main, so if 1.9.0 had a fix, your fork may have re-exposed the vulnerability.
- **If MISSING/PARTIAL — required change set:**
  - Requires investigation of what Langflow 1.9.0 actually changed in `src/lfx/src/lfx/custom/validate.py` to mitigate dynamic `exec()` in validation.
  - The fix likely involves one of:
    1. Removing dynamic class instantiation from validation (static syntax checks only), or
    2. Running `create_class()` in a restricted sandbox/jail environment, or
    3. Disabling the feature entirely for untrusted inputs.
  - Current fork still has unrestricted `exec()` in `create_class()` and `build_class_constructor()`.
- **Follow-up / open questions (if any):**
  - Did the 2026-04-15 revert of release 1.9.0 re-expose this critical RCE vulnerability?
  - What is the intended fix in 1.9.0? Is it a behavioral change (static validation only) or a runtime sandbox?

---

## GHSA-8c4j-f57c-35cf — CVE-2026-34046 — Authenticated Users Can Read, Modify, and Delete Any Flow via Missing Ownership Check

- **Severity:** high
- **Published:** 2026-04
- **Patched upstream in:** >= 1.5.1 (PR #8956)
- **Upstream fix reference:** PR #8956 removes the conditional `AUTO_LOGIN` branching logic in `_read_flow()` and unconditionally scopes all queries to `Flow.user_id == user_id`, preventing cross-user flow access.
- **Verdict:** APPLIED
- **Evidence:**
  - PR #8956 was cherry-picked to `platform-multi-tenant` (commits d437d018ce and 7bc5957c04).
  - Current code in `src/backend/base/langflow/api/v1/flows.py:534-544` shows:
    ```python
    async def _read_flow(
        session: AsyncSession,
        flow_id: UUID,
        user_id: UUID,
        organization_id: UUID | None = None,
    ):
        """Read a flow, scoped to user_id and (if provided) organization_id."""
        stmt = select(Flow).where(Flow.id == flow_id).where(Flow.user_id == user_id)
        if organization_id is not None:
            stmt = stmt.where(Flow.organization_id == organization_id)
        return (await session.exec(stmt)).first()
    ```
  - This unconditionally enforces `Flow.user_id == user_id` on all flows accessed via this helper, preventing the IDOR.
  - Additional security work in fork-side `src/backend/base/langflow/api/v1/templates.py` (cross-org scoping) complements this fix with multi-tenant awareness.

---

## Summary Table

| # | GHSA | CVE | Severity | Title | Verdict | Status |
|---|------|-----|----------|-------|---------|--------|
| 1 | GHSA-7grx-3xcx-2xv5 | CVE-2026-33484 | high | Unauthenticated IDOR on Image Downloads | **PARTIAL** | Reverted 2026-04-15 |
| 2 | GHSA-ph9w-r52h-28p7 | CVE-2026-33497 | medium | /profile_pictures/{folder_name}/{file_name} endpoint file reading | **APPLIED** | ✓ Secure |
| 3 | GHSA-v8hw-mh8c-jxfc | CVE-2026-33873 | critical | Authenticated Code Execution in Agentic Assistant Validation | **UNCERTAIN** | Requires investigation |
| 4 | GHSA-8c4j-f57c-35cf | CVE-2026-34046 | high | Authenticated Users Can Read, Modify, and Delete Any Flow | **APPLIED** | ✓ Secure |

### Action Items

- **Advisory #1 (PARTIAL):** Restore the ownership check to `/images/{flow_id}/{file_name}` endpoint by re-applying PR #12234's changes to `download_image()`.
- **Advisory #3 (UNCERTAIN):** Investigate whether the 2026-04-15 revert exposed the critical RCE vulnerability. Compare your fork's `lfx/custom/validate.py` with upstream 1.9.0 to confirm the fix is present or was lost.


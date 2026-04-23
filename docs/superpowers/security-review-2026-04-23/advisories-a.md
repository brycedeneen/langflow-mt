# Advisory Group A — Research Report (2025 + early 2026)

**Reviewer agent:** Explore
**Date:** 2026-04-23
**Branch:** platform-multi-tenant
**Working dir:** /Users/brycedeneen/dev/langflow

---

## GHSA-rvqx-wpfh-mfx7 — CVE-2025-3248 — Langflow Unauth RCE

- **Severity:** critical
- **Published:** 2025-06-17
- **Patched upstream in:** Langflow 1.3.0
- **Upstream fix reference:** Fixed code injection in `/api/v1/validate/code` endpoint by requiring authentication.
- **Verdict:** APPLIED
- **Evidence:** 
  - Our fork's `/api/v1/validate/code` endpoint at `src/backend/base/langflow/api/v1/validate.py:17` has the dependency `dependencies=[Depends(get_current_active_user)]` applied, requiring authentication.
  - The code is gated behind authentication, preventing unauthenticated code execution.
  - This is a base protection present in any fork descended from Langflow 1.3.0+.
- **Follow-up / open questions (if any):** None.

---

## GHSA-4gv9-mp8m-592r — CVE-2025-57760 — Privilege Escalation via CLI Superuser Creation (Post-RCE)

- **Severity:** high
- **Published:** 2025-08-25
- **Patched upstream in:** Langflow (version not specified in advisory, but fix is in `_create_superuser` function)
- **Upstream fix reference:** Added authentication requirements for superuser CLI creation; requires either AUTO_LOGIN mode (first setup only) or valid superuser token.
- **Verdict:** APPLIED
- **Evidence:**
  - CLI superuser command at `src/backend/base/langflow/__main__.py:705-816` validates multiple security conditions:
    - Line 711-714: Checks if `ENABLE_SUPERUSER_CLI` is true (disabled by default).
    - Line 736-744: In AUTO_LOGIN mode, prevents additional superuser creation after first setup.
    - Line 753-757: In production mode, requires `--auth-token` parameter.
    - Line 760-778: Validates token is from a superuser (JWT or API key).
  - These guards prevent privilege escalation from arbitrary RCE.
- **Follow-up / open questions (if any):** None.

---

## GHSA-5993-7p27-66g5 — CVE-2025-68477 — SSRF in langflow-ai/langflow

- **Severity:** high
- **Published:** 2025-12-19
- **Patched upstream in:** Langflow (SSRF protection feature; see PR #11996, #12516)
- **Upstream fix reference:** Added `ssrf_protection.py` module with configurable SSRF blocking for private/internal IP ranges. API Request component validates URLs via `validate_url_for_ssrf()`.
- **Verdict:** APPLIED
- **Evidence:**
  - SSRF protection module present at `src/lfx/src/lfx/utils/ssrf_protection.py` with comprehensive validation:
    - Blocks IPv4 RFC 1918 ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16).
    - Blocks loopback (127.0.0.0/8, ::1/128).
    - Blocks AWS metadata (169.254.0.0/16).
    - Blocks cloud/special ranges (224.0.0.0/4, 240.0.0.0/4, etc.).
    - Supports allowlist via `LANGFLOW_SSRF_ALLOWED_HOSTS` env var.
    - Default: warn_only=True (non-blocking), intended to become blocking in v2.0.
  - API Request component at `src/lfx/src/lfx/components/data_source/api_request.py:555-556` calls `validate_url_for_ssrf()`.
  - Git history shows multiple SSRF commits: commits e146f418ff, 9a950fc66f, 7b84a7e426 on `platform-multi-tenant`.
- **Follow-up / open questions (if any):** SSRF protection is currently `warn_only=True` by default (does not block). Configuration flag `LANGFLOW_SSRF_PROTECTION_ENABLED` defaults to false per `.../ssrf_protection.py:16`. This is intentional per the TODO comment to enforce blocking in v2.0.

---

## GHSA-f43r-cc68-gpx4 — CVE-2025-68478 — External Control of File Name or Path

- **Severity:** high
- **Published:** 2025-12-19
- **Patched upstream in:** Langflow (path traversal protection in flows endpoint)
- **Upstream fix reference:** Added `_get_safe_flow_path()` and `_verify_fs_path()` functions that validate and normalize fs_path to prevent directory traversal.
- **Verdict:** APPLIED
- **Evidence:**
  - Path validation function at `src/backend/base/langflow/api/v1/flows.py:70-147` (`_get_safe_flow_path()`):
    - Line 82-86: Rejects paths with ".." (directory traversal).
    - Line 87-91: Rejects paths with null bytes.
    - Line 93-129: Enforces base directory confinement using `resolve()` and `relative_to()` checks.
    - Line 131-147: Prevents symlink attacks by resolving and verifying final path stays within base.
  - Called from `_new_flow()` at line 240 and `_save_flow_to_fs()` at line 168.
  - All flow creation and updates validate `fs_path` before filesystem write.
- **Follow-up / open questions (if any):** None.

---

## GHSA-c5cp-vx83-jhqx — CVE-2026-21445 — Missing Authentication on Critical API Endpoints

- **Severity:** critical
- **Published:** 2026-01-02
- **Patched upstream in:** Langflow (commit f5629bccb3, PR #12202)
- **Upstream fix reference:** Added authentication dependencies to monitor endpoints: `/api/v1/monitor/messages` (line 69), `/api/v1/monitor/transactions` (line 191), and `/api/v1/monitor/messages/session/{session_id}` (line 174). Also added message/flow ownership scoping.
- **Verdict:** APPLIED
- **Evidence:**
  - Monitor endpoints at `src/backend/base/langflow/api/v1/monitor.py`:
    - Line 66-75 (GET `/messages`): Has `current_user: Annotated[User, Depends(get_current_active_user)]` parameter (line 69) and scopes data to `Flow.user_id == current_user.id` (line 80).
    - Line 191 (GET `/transactions`): Has `dependencies=[Depends(get_current_active_user)]` (line 191).
    - Line 174 (DELETE `/messages/session/{session_id}`): Has `dependencies=[Depends(get_current_active_user)]` (line 174) and scopes deletion to flows owned by user.
  - Commit f5629bccb3 visible in git log on `platform-multi-tenant` (fix: enforce message ownership in monitor endpoints (#12202)).
  - All endpoints require authentication and scope access to authenticated user's resources.
- **Follow-up / open questions (if any):** None.

---

## Summary

| Advisory | Verdict | Severity |
|----------|---------|----------|
| GHSA-rvqx-wpfh-mfx7 | APPLIED | critical |
| GHSA-4gv9-mp8m-592r | APPLIED | high |
| GHSA-5993-7p27-66g5 | APPLIED | high |
| GHSA-f43r-cc68-gpx4 | APPLIED | high |
| GHSA-c5cp-vx83-jhqx | APPLIED | critical |

# User Detail & Roles — Follow-ups (Post-Merge)

Items surfaced during implementation that were deliberately deferred. Not blocking the initial merge. Each has enough context to start a focused follow-up PR.

## FU-1. Reconcile `is_superuser` vs `is_platform_admin` gate on `PATCH /api/v1/users/{user_id}`

**Discovered:** Phase 2, Task 9.

**The issue:** The existing user PATCH endpoint (`src/backend/base/langflow/api/v1/users.py:79-107`) gates on `is_superuser`. The new admin surface (`/api/v1/admin/**`) gates on `is_platform_admin`. Because the two flags can diverge (platform admins created after the `platform-admin` data-migration are not automatically superusers), the **AccountTab** on the new User Detail Page will 403 when a platform-admin-only caller tries to toggle `is_active` / `is_platform_admin` / `username` on another user.

**Symptoms users will see:**
- Platform admin opens `/admin/users/:userId` → Account tab loads (reads `GET /admin/users/{user_id}` — works).
- They flip the Active switch → PATCH fires → 403 (non-superuser modifying another user).

**Options:**
- **A.** Extend the existing PATCH gate to accept platform admins: `if not (user.is_superuser or user.is_platform_admin) and user.id != user_id: raise 403`.
- **B.** Add a parallel PATCH endpoint under `/api/v1/admin/users/{user_id}` that gates on `PlatformAdmin` and reuses the CRUD helper. Cleaner separation between "user self-service" and "platform-admin user management."
- **C.** Policy: platform admins must also be superusers. Makes existing gate a no-op change. Documented-only fix.

**Recommendation:** Option B. Keeps the platform-admin surface cohesive under `/admin/*` and avoids shifting the semantics of the existing endpoint used by the current `UsersPage`.

**Affected tests/UI:**
- Frontend `AccountTab` will need to swap to the new endpoint (if Option B) or just continue using the existing one (Options A, C).
- Add a test verifying platform-admin-only caller can flip `is_active` and `is_platform_admin`.

## FU-2. Last-Owner TOCTOU race on `PATCH` role change and `DELETE` member

**Discovered:** Phase 2, Tasks 6 and 7, flagged by code reviewer both times.

**The issue:** Both `patch_member_role` and `remove_member` implement the last-owner guard with a SELECT-COUNT-then-modify pattern:

```python
if m.role == OWNER and new_role != OWNER:
    owner_count = SELECT COUNT(*) FROM membership WHERE org_id = ? AND role = 'owner'
    if owner_count <= 1: raise 409
    # ... then UPDATE role ...
```

Two concurrent privileged callers demoting/removing two different Owners can both read `count == 2`, both pass the guard, and both succeed — leaving an org with zero Owners. This violates the invariant "≥ 1 Owner per non-personal org."

**Realistic exposure:** Low. The frontend `RolePicker` issues one mutation at a time, and most orgs have a single admin. But a scripted client or two admin browser tabs can trigger it.

**Options:**
- **A.** `SELECT ... FOR UPDATE` on the target Owner rows (Postgres); no-op on SQLite. One-line change in both endpoints.
- **B.** DB-level partial index or trigger enforcing the invariant. Heavier (needs migration), catches all call sites including future ones.
- **C.** Serializable isolation on these two endpoints only. Heaviest, but future-proof.

**Recommendation:** Start with Option A. Revisit if we see reports or add automated role-change tooling. Add a shared `# TODO(concurrency)` comment at both call sites noting the race and the planned mitigation.

**Affected files:**
- `src/backend/base/langflow/api/v1/admin/orgs.py` — `patch_member_role` (lines ~435-445), `remove_member` (similar block).

## FU-3. Postgres `ALTER TYPE ADD VALUE` not runtime-validated locally

**Discovered:** Phase 1, Task 2.

**The issue:** The enum-extension migration (`d882b36fff8d_extend_membership_role_enum.py`) emits `ALTER TYPE membership_role_enum ADD VALUE IF NOT EXISTS` in the Postgres branch. We only have SQLite locally, so that branch was never actually executed against a real Postgres during development. Code-inspection shows correct syntax, but the first live run will be in production.

**Risk:** On Postgres 11 and earlier, `ALTER TYPE ADD VALUE` inside an alembic-wrapped transaction raises. Postgres 12+ permits it. If our deployment target is pinned to 12+, this is a non-issue.

**Options:**
- **A.** Verify the deployment Postgres version is ≥12 (likely yes) and document that finding in the migration docstring.
- **B.** Wrap the loop in `op.get_context().autocommit_block()` defensively. Works on all Postgres versions, no downside.

**Recommendation:** Option B — one extra line, zero downside, removes the version dependency entirely.

**Affected files:**
- `src/backend/base/langflow/alembic/versions/d882b36fff8d_extend_membership_role_enum.py`.

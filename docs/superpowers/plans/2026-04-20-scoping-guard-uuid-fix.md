# `_insert_guard` UUID-format fix — stop double-provisioning personal orgs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One new user = exactly one personal org + one membership, on both SQLite and Postgres. Un-xfail the 3 Tier 2 tests that were pinned to this bug.

**Architecture:** The `before_insert` hook in `scoping.py::_insert_guard` does three UUID-keyed SELECTs (`flow.id`, `folder.id`, `membership.user_id`) using `str(uuid_obj)`, which renders the dashed form `'xxxxxxxx-xxxx-…'`. SQLAlchemy's UUID type column stores UUIDs on SQLite as lowercase 32-char hex **without** dashes, so each SELECT misses even when the row exists. In the `user_id` case the guard then auto-provisions a *second* personal org + membership via raw SQL (`_as_hex` — the correct format) — and every later lookup for the same user finds *that* duplicate first, leaving the user with two `is_personal=True` orgs. `get_current_organization`'s personal-org preference is non-deterministic when two personal orgs exist, so the default folder's `organization_id` and the request's `current_org` end up pointing at different orgs and tenant-scoped list queries return empty. Postgres dodges this by accepting either UUID string form; SQLite (dev + tests) does not.

Fix: use `_as_hex(...)` at all three SELECT sites in `_insert_guard`, matching what `_user_after_insert` already does on the write path. Add a defensive `min(by created_at)` tiebreaker to `get_current_organization` so the personal-org pick is deterministic even if legacy duplicate state survives.

**Tech Stack:** Python · SQLAlchemy / SQLModel · SQLite (dev + tests) · Postgres (prod) · pytest · Alembic (no DDL needed — the fix is data-path only).

---

## File structure

**Modify (3):**
- `src/backend/base/langflow/services/database/scoping.py` — lines 188–216 (three `str(...)` → `_as_hex(...)` swaps inside `_insert_guard`)
- `src/backend/base/langflow/api/utils/org_helpers.py` — lines 43–46 (deterministic tiebreaker among personal orgs)
- `src/backend/tests/unit/api/v1/test_folders.py`, `test_projects.py`, `test_flow_folder_integrity.py` — remove the three `@pytest.mark.xfail` blocks added in commit `f6101e5978`

**Create (1):**
- `src/backend/tests/unit/services/database/test_scoping_guard.py` — regression test for the UUID-format bug and the tiebreaker

No model, no migration, no schema change. Pure behavior fix.

---

## Task 1: Lock in the bug with a failing regression test

**Files:**
- Create: `src/backend/tests/unit/services/database/__init__.py` (empty, if missing)
- Create: `src/backend/tests/unit/services/database/test_scoping_guard.py`

- [ ] **Step 1: Confirm the directory / `__init__.py` exists**

```bash
ls src/backend/tests/unit/services/database/__init__.py 2>/dev/null || \
  : > src/backend/tests/unit/services/database/__init__.py
```

- [ ] **Step 2: Write the failing test**

Create `src/backend/tests/unit/services/database/test_scoping_guard.py`:

```python
"""Regression tests for langflow.services.database.scoping guards.

The `_insert_guard` before-insert hook auto-provisions a personal org +
membership for tenant-scoped inserts whose `user_id` has no membership yet.
It must be idempotent against a User that was *already* given a personal org
by `_user_after_insert` — otherwise the user ends up with two personal orgs
and `get_current_organization` becomes non-deterministic.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.membership.model import Membership
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from sqlmodel import select


@pytest.mark.asyncio
async def test_insert_guard_does_not_duplicate_personal_org(client):  # noqa: ARG001
    """A fresh User + one tenant-scoped insert must leave exactly 1 membership.

    Prior bug: `_insert_guard` used `str(user_id)` in its SELECT, which on
    SQLite does not match the 32-char-no-dash form SQLAlchemy stores. The
    lookup missed, the guard provisioned a second personal org, and the user
    ended up with two.
    """
    async with session_scope() as session:
        user = User(username=f"guard-test-{uuid4().hex[:8]}", password="x", is_active=True)
        session.add(user)
        await session.flush()
        await session.refresh(user)
        user_id = user.id

        # Memberships immediately after user insert — must be exactly 1
        # (_user_after_insert auto-provisioned it).
        mship_after_user = (
            await session.exec(select(Membership).where(Membership.user_id == user_id))
        ).all()
        assert len(mship_after_user) == 1, (
            f"_user_after_insert must provision exactly one membership, got {len(mship_after_user)}"
        )

        # Now force the before_insert guard to run by inserting a tenant-scoped
        # row (Folder) with no organization_id. The guard should resolve it
        # from the existing membership — not provision a new one.
        folder = Folder(user_id=user_id, name="guard-test-folder")
        session.add(folder)
        await session.flush()
        await session.refresh(folder)

        mship_after_folder = (
            await session.exec(select(Membership).where(Membership.user_id == user_id))
        ).all()
        assert len(mship_after_folder) == 1, (
            f"_insert_guard must reuse the existing membership, got {len(mship_after_folder)} "
            f"(guard over-provisioned a duplicate)"
        )

        # And the folder must have been tagged with that same org.
        assert folder.organization_id == mship_after_folder[0].organization_id, (
            "Folder landed in a different org than the user's membership"
        )


@pytest.mark.asyncio
async def test_insert_guard_resolves_via_folder_id(client):  # noqa: ARG001
    """If the row has a folder_id, the guard must resolve via folder, not user_id.

    This covers the same UUID-format bug on the folder lookup path.
    """
    async with session_scope() as session:
        user = User(username=f"guard-folder-{uuid4().hex[:8]}", password="x", is_active=True)
        session.add(user)
        await session.flush()

        folder = Folder(user_id=user.id, name="parent-folder")
        session.add(folder)
        await session.flush()
        await session.refresh(folder)
        parent_folder_id = folder.id
        parent_folder_org = folder.organization_id
        assert parent_folder_org is not None

        # A child insert (flow) that has a folder_id but no organization_id
        # should inherit the folder's org — not fall through to the user_id
        # branch (which would work, but only by accident).
        from langflow.services.database.models.flow.model import Flow

        flow = Flow(user_id=user.id, folder_id=parent_folder_id, name="child-flow", data={})
        session.add(flow)
        await session.flush()
        await session.refresh(flow)

        assert flow.organization_id == parent_folder_org, (
            "Flow must inherit organization_id from its folder"
        )

        # The user should STILL have exactly one membership — the folder
        # lookup succeeded so the guard never hit the provisioning path.
        memberships = (
            await session.exec(select(Membership).where(Membership.user_id == user.id))
        ).all()
        assert len(memberships) == 1, f"Expected 1 membership, got {len(memberships)}"


@pytest.mark.asyncio
async def test_get_current_organization_prefers_oldest_personal_org(client, active_user):  # noqa: ARG001
    """When two personal orgs somehow survive for a user, pick the oldest.

    Covers the defensive tiebreaker added to `get_current_organization` so
    legacy duplicate state doesn't produce non-deterministic org picks.
    """
    from datetime import datetime, timedelta, timezone

    from langflow.api.utils.org_helpers import get_current_organization

    async with session_scope() as session:
        # Give active_user a *second* personal org + membership deliberately
        # to simulate the legacy-duplicate state.
        newer = Organization(
            name=f"fake-dup-{uuid4().hex[:8]}",
            slug=f"fake-dup-{uuid4().hex[:8]}",
            is_personal=True,
            created_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        session.add(newer)
        await session.flush()
        session.add(Membership(user_id=active_user.id, organization_id=newer.id))
        await session.commit()

        org = await get_current_organization(user=active_user, session=session, x_acting_org_id=None)

    # Must pick the oldest personal org, not `newer`.
    assert org.id != newer.id, (
        "get_current_organization picked the newer duplicate personal org; "
        "tiebreaker should prefer the earliest-created one."
    )
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
uv run --no-sync pytest src/backend/tests/unit/services/database/test_scoping_guard.py -v --no-header 2>&1 | tail -20
```

Expected: `test_insert_guard_does_not_duplicate_personal_org` FAILS with `len(mship_after_folder) == 2` (or similar). `test_insert_guard_resolves_via_folder_id` may FAIL or pass by accident. `test_get_current_organization_prefers_oldest_personal_org` FAILS (tiebreaker not yet implemented).

- [ ] **Step 4: Commit the failing test**

```bash
git add src/backend/tests/unit/services/database/__init__.py src/backend/tests/unit/services/database/test_scoping_guard.py
git commit -m "test(scoping): regression for _insert_guard UUID-format bug"
```

Pause here and ask the user before committing — no auto-commit per memory `feedback_no_git_commits`.

---

## Task 2: Fix `_insert_guard` — use `_as_hex` at all 3 SELECT sites

**Files:**
- Modify: `src/backend/base/langflow/services/database/scoping.py` lines 188–216

- [ ] **Step 1: Apply the three-line fix**

In `src/backend/base/langflow/services/database/scoping.py`, inside `_insert_guard`, change:

```python
        # Resolve via flow_id → flow.organization_id (covers transaction/message/vertex_build/
        # flow_version/job which have no direct user_id).
        flow_id = getattr(target, "flow_id", None)
        if flow_id is not None:
            row = connection.execute(
                text("SELECT organization_id FROM flow WHERE id = :fid"),
                {"fid": str(flow_id)},
            ).first()
```

to:

```python
        # Resolve via flow_id → flow.organization_id (covers transaction/message/vertex_build/
        # flow_version/job which have no direct user_id).
        flow_id = getattr(target, "flow_id", None)
        if flow_id is not None:
            row = connection.execute(
                text("SELECT organization_id FROM flow WHERE id = :fid"),
                {"fid": _as_hex(flow_id)},
            ).first()
```

Same change for the folder branch:

```python
        # Resolve via folder_id → folder.organization_id.
        folder_id = getattr(target, "folder_id", None)
        if folder_id is not None:
            row = connection.execute(
                text("SELECT organization_id FROM folder WHERE id = :fid"),
                {"fid": str(folder_id)},
            ).first()
```

→

```python
        # Resolve via folder_id → folder.organization_id.
        folder_id = getattr(target, "folder_id", None)
        if folder_id is not None:
            row = connection.execute(
                text("SELECT organization_id FROM folder WHERE id = :fid"),
                {"fid": _as_hex(folder_id)},
            ).first()
```

And the user_id branch:

```python
        user_id = getattr(target, "user_id", None)
        if user_id is not None:
            uid_str = str(user_id)
            row = connection.execute(
                text("SELECT organization_id FROM membership WHERE user_id = :uid LIMIT 1"),
                {"uid": uid_str},
            ).first()
```

→

```python
        user_id = getattr(target, "user_id", None)
        if user_id is not None:
            uid_str = _as_hex(user_id)
            row = connection.execute(
                text("SELECT organization_id FROM membership WHERE user_id = :uid LIMIT 1"),
                {"uid": uid_str},
            ).first()
```

The subsequent raw-SQL INSERTs on lines 221–239 already consume `uid_str`, so they now receive hex-formatted input and continue working on both SQLite (direct match) and Postgres (UUID type accepts hex).

- [ ] **Step 2: Run the regression test to verify the fix**

```bash
uv run --no-sync pytest src/backend/tests/unit/services/database/test_scoping_guard.py::test_insert_guard_does_not_duplicate_personal_org src/backend/tests/unit/services/database/test_scoping_guard.py::test_insert_guard_resolves_via_folder_id -v --no-header 2>&1 | tail -10
```

Expected: Both PASS. `test_get_current_organization_prefers_oldest_personal_org` still FAILS (that's Task 3).

- [ ] **Step 3: Confirm Postgres compatibility**

`_as_hex` accepts both `UUID` objects and strings, and returns 32-char hex. Postgres's UUID type parses hex unambiguously (no hyphens required; it's documented as `A4xxxxxx…` or `a4xx-xxxx-…` — both valid). Sanity-check by reading `_as_hex`:

```bash
uv run --no-sync python -c "
from uuid import uuid4
from langflow.services.database.scoping import _as_hex
u = uuid4()
print(f'UUID: {u}')
print(f'_as_hex: {_as_hex(u)}')
print(f'str:     {str(u)}')
"
```

Expected output shows the hex form is 32 chars, no dashes.

- [ ] **Step 4: Commit**

```bash
git add src/backend/base/langflow/services/database/scoping.py
git commit -m "fix(scoping): use _as_hex at all insert-guard lookup sites

SQLAlchemy's UUID column on SQLite stores CHAR(32) lowercase hex without
dashes. The three SELECTs in _insert_guard bound str(uuid_obj) which renders
the dashed form and never matches, so the guard provisioned a second personal
org + membership for every newly created user on the user_id path (and
incorrectly fell through to user_id on the flow_id / folder_id paths).

Match the write path (_as_hex) at all three lookup sites so the guard is
idempotent on SQLite and Postgres alike."
```

Pause and ask before committing.

---

## Task 3: Defensive tiebreaker in `get_current_organization`

**Files:**
- Modify: `src/backend/base/langflow/api/utils/org_helpers.py` lines 42–46

- [ ] **Step 1: Apply the fix**

Change:

```python
    # Prefer the user's personal org; else the earliest-created one.
    personal = next((o for o in orgs if o.is_personal), None)
    if personal is not None:
        return personal
    return min(orgs, key=lambda o: o.created_at)
```

to:

```python
    # Prefer the user's personal org; if multiple (legacy duplicate state),
    # pick the earliest-created so the choice is deterministic. Otherwise
    # fall back to the earliest-created org overall.
    personal_orgs = [o for o in orgs if o.is_personal]
    if personal_orgs:
        return min(personal_orgs, key=lambda o: o.created_at)
    return min(orgs, key=lambda o: o.created_at)
```

- [ ] **Step 2: Run the tiebreaker test**

```bash
uv run --no-sync pytest src/backend/tests/unit/services/database/test_scoping_guard.py::test_get_current_organization_prefers_oldest_personal_org -v --no-header 2>&1 | tail -10
```

Expected: PASS.

- [ ] **Step 3: Run the full new test module**

```bash
uv run --no-sync pytest src/backend/tests/unit/services/database/test_scoping_guard.py -v --no-header 2>&1 | tail -10
```

Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add src/backend/base/langflow/api/utils/org_helpers.py
git commit -m "fix(org_helpers): deterministic personal-org pick among duplicates

get_current_organization used next(..., is_personal) which depends on row
iteration order — non-deterministic when a user somehow carries two personal
orgs (pre-fix _insert_guard state, or future multi-org work). Tiebreak by
earliest created_at, matching the non-personal fallback."
```

Pause and ask before committing.

---

## Task 4: Un-xfail the three Tier 2 tests and confirm they're green

**Files:**
- Modify: `src/backend/tests/unit/api/v1/test_folders.py` — remove `@pytest.mark.xfail` on `test_read_folders`
- Modify: `src/backend/tests/unit/api/v1/test_projects.py` — remove `@pytest.mark.xfail` on `test_read_projects`
- Modify: `src/backend/tests/unit/api/v1/test_flow_folder_integrity.py` — remove `@pytest.mark.xfail` on `test_flow_created_is_retrievable_in_folder`

- [ ] **Step 1: Remove the xfail from `test_folders.py`**

Delete the `@pytest.mark.xfail(...)` block immediately above `async def test_read_folders`. The reason text and `strict=False` kwargs both go. After the edit the function declaration should be the first line of that test (no decorator).

- [ ] **Step 2: Remove the xfail from `test_projects.py`**

Same — strip the block above `async def test_read_projects`.

- [ ] **Step 3: Remove the xfail from `test_flow_folder_integrity.py`**

Same — strip the block above `async def test_flow_created_is_retrievable_in_folder`. Also remove the now-unused `import pytest` at the top if it becomes orphan (it is referenced elsewhere in that file — leave alone).

- [ ] **Step 4: Run the three formerly-xfailed tests**

```bash
uv run --no-sync pytest \
  src/backend/tests/unit/api/v1/test_folders.py::test_read_folders \
  src/backend/tests/unit/api/v1/test_projects.py::test_read_projects \
  src/backend/tests/unit/api/v1/test_flow_folder_integrity.py::test_flow_created_is_retrievable_in_folder \
  -v --no-header 2>&1 | tail -10
```

Expected: 3 PASSED, 0 failed, 0 xfailed.

- [ ] **Step 5: Commit**

```bash
git add src/backend/tests/unit/api/v1/test_folders.py src/backend/tests/unit/api/v1/test_projects.py src/backend/tests/unit/api/v1/test_flow_folder_integrity.py
git commit -m "test: un-xfail folder/project listing tests after scoping fix"
```

Pause and ask before committing.

---

## Task 5: Broad regression sweep

- [ ] **Step 1: Re-run the full Tier 2 bundle**

```bash
uv run --no-sync pytest \
  src/backend/tests/unit/agentic/utils/test_template_search.py \
  src/backend/tests/unit/services/tracing/test_repository.py \
  src/backend/tests/unit/test_assistant_mutation.py \
  src/backend/tests/unit/api/v1/test_folders.py \
  src/backend/tests/unit/api/v1/test_projects.py \
  src/backend/tests/unit/api/v1/test_flow_folder_integrity.py \
  src/backend/tests/unit/api/v2/test_mcp_servers_file.py \
  src/backend/tests/test_starter_projects.py \
  src/backend/tests/unit/template/test_starter_projects.py \
  src/backend/tests/unit/services/database/test_scoping_guard.py \
  --no-header -q 2>&1 | tail -3
```

Expected: all passed, 0 xfailed (previously 3).

- [ ] **Step 2: Re-run the Tier 1 bundle to confirm the scoping change didn't regress anything**

```bash
uv run --no-sync pytest \
  src/backend/tests/unit/test_webhook.py \
  src/backend/tests/unit/api/v1/test_webhook_distributed.py \
  src/backend/tests/unit/test_user.py \
  src/backend/tests/unit/services/flow/test_flow_runner.py \
  src/backend/tests/unit/alembic/test_migration_execution.py \
  src/backend/tests/unit/test_session_endpoint.py \
  --no-header -q 2>&1 | tail -3
```

Expected: all passed, no new failures.

- [ ] **Step 3: Run the broader `scoping`-touching surface to catch anything subtler**

```bash
uv run --no-sync pytest src/backend/tests/unit/api/v1/ src/backend/tests/unit/api/v2/ --no-header -q 2>&1 | tail -5
```

Expected: the same pass/skip/xfail ratio as before the fix, minus the 3 un-xfailed ones.

- [ ] **Step 4: No separate commit — the fix commits already stand**

---

## Out of scope (intentional, flag as follow-ups if observed in prod)

- **Data repair for dev/prod users already carrying duplicate personal orgs.** Postgres accepts both UUID string forms, so the bug's blast radius is limited to SQLite-backed environments; any Postgres user who has duplicate memberships got them via some *other* path and needs independent investigation. Adding a sweep-and-merge alembic migration is non-trivial (must re-parent every tenant-scoped table's rows to the keeper org, respect FK order, handle unique constraints) and is better deferred to a dedicated task once we know who is affected.
- **`_insert_guard` flow_id-lookup on Postgres.** The fix makes flow_id / folder_id lookups use hex, which Postgres tolerates. If a future Postgres migration ever stores UUIDs in a string column (not native `uuid`), this code keeps working — but no such migration is planned.
- **Rewriting `_insert_guard`'s auto-provisioning as a session-commit hook.** The current best-effort inline provisioning is adequate once the format bug is gone; refactoring to a cleaner hook is a quality-of-life task, not a correctness fix.

---

## Self-review notes

- Spec coverage: bug fix (Task 2), tiebreaker (Task 3), regression test (Task 1), un-xfail (Task 4), sweep (Task 5). ✓
- No placeholders. Every code block is final text. ✓
- Type consistency: `_as_hex` signature matches its existing definition (`value → str | None`); `get_current_organization` return type unchanged. ✓
- Commit steps all pause per memory `feedback_no_git_commits`. ✓

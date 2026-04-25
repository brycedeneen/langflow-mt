# SecretStore.list() Contract Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pin the `SecretStore.list()` contract to Vault KV v2 LIST semantics (immediate children, sub-dirs end with `/`), align `InMemorySecretStore` to match, and drop the `_list_autosecret_paths` workaround.

**Architecture:** Update the ABC docstring in `base.py`, rewrite `InMemorySecretStore.list` in `factory.py`, and inline the two-level walk inside `auto_secrets.py`'s cleanup/delete functions. `VaultSecretStore` stays unchanged (already correct).

**Tech Stack:** Python 3.12, pytest, pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-04-25-secret-store-list-contract-design.md`

---

## Task 1: Pin the ABC contract + align the test stub

**Files:**
- Modify: `src/lfx/src/lfx/services/secret_store/base.py`
- Modify: `src/lfx/tests/unit/services/test_secret_store.py`

- [ ] **Step 1: Update the failing test for the new contract**

In `src/lfx/tests/unit/services/test_secret_store.py`, locate `ConcreteSecretStore` (around line 8) and `TestSecretStoreABC.test_list_by_prefix` (around line 55) / `test_list_empty_prefix` (around line 64).

Replace the `ConcreteSecretStore.list` body with the new contract behavior (relative children, sub-dirs end with `/`). It must mirror what `InMemorySecretStore` will do in Task 2 — both implementations share the same shape:

```python
async def list(self, prefix: str) -> list[str]:
    seen: set[str] = set()
    for key in self._store:
        if not key.startswith(prefix):
            continue
        rest = key[len(prefix):]
        if not rest:
            continue
        head, sep, _ = rest.partition("/")
        seen.add(head + ("/" if sep else ""))
    return sorted(seen)
```

Update the existing list tests to assert against the new contract, and add a new test covering directory markers:

```python
@pytest.mark.asyncio
async def test_list_by_prefix(self):
    store = ConcreteSecretStore()
    await store.put("org1/webhooks/flow1", {"key": "a"})
    await store.put("org1/webhooks/flow2", {"key": "b"})
    await store.put("org2/webhooks/flow3", {"key": "c"})
    # Immediate children of "org1/webhooks/" are leaf names (no trailing /).
    result = await store.list("org1/webhooks/")
    assert result == ["flow1", "flow2"]


@pytest.mark.asyncio
async def test_list_empty_prefix(self):
    store = ConcreteSecretStore()
    result = await store.list("nonexistent/")
    assert result == []


@pytest.mark.asyncio
async def test_list_returns_directory_markers_for_subdirs(self):
    """Sub-directory entries end with `/`; leaves don't."""
    store = ConcreteSecretStore()
    await store.put("a/b/c", {"v": 1})
    await store.put("a/b/d", {"v": 2})
    await store.put("a/e", {"v": 3})
    # At "a/", the children are "b/" (subdir) and "e" (leaf).
    assert await store.list("a/") == ["b/", "e"]
    # At "a/b/", both children are leaves.
    assert await store.list("a/b/") == ["c", "d"]


@pytest.mark.asyncio
async def test_list_excludes_exact_match_prefix(self):
    """A key that equals the prefix is not its own child."""
    store = ConcreteSecretStore()
    await store.put("a/b/", {"v": 1})  # key with trailing /
    await store.put("a/b/c", {"v": 2})
    # The "a/b/" key is the directory itself (not a child); "c" is the only child.
    assert await store.list("a/b/") == ["c"]
```

- [ ] **Step 2: Run, confirm fail**

```
uv run pytest src/lfx/tests/unit/services/test_secret_store.py::TestSecretStoreABC -v
```
Expected: the existing `test_list_by_prefix` may already be updated (passing), but `test_list_returns_directory_markers_for_subdirs` and `test_list_excludes_exact_match_prefix` MUST FAIL until `ConcreteSecretStore.list` is rewritten in Step 1. (If you wrote the new `ConcreteSecretStore.list` body in Step 1, both new tests should immediately PASS — that's fine; this task primarily pins the contract via the test stub.)

If all tests pass already, that's the expected outcome — Step 1 already aligned the test stub to the new contract.

- [ ] **Step 3: Pin the ABC docstring**

In `src/lfx/src/lfx/services/secret_store/base.py`, update the `list` method's docstring:

```python
@abstractmethod
async def list(self, prefix: str) -> list[str]:
    """List immediate children under a prefix (KV v2 LIST semantics).

    Returns relative names — sub-directory entries end with `/`, leaf
    entries do not. Callers walking deeper structure must recurse explicitly.

    Example:
        Store has keys: ["a/b/c", "a/b/d", "a/e"].
        store.list("a/")  → ["b/", "e"]
        store.list("a/b/") → ["c", "d"]
    """
```

- [ ] **Step 4: Run all SecretStore unit tests**

```
uv run pytest src/lfx/tests/unit/services/test_secret_store.py -v
```
Expected: all PASS. The Vault tests (`TestVaultSecretStore.test_list_returns_keys`, `test_list_empty_returns_empty`) are unaffected — they mock the underlying client; their assertions on the relative-children shape were already correct.

- [ ] **Step 5: Commit**

```bash
git add \
  src/lfx/src/lfx/services/secret_store/base.py \
  src/lfx/tests/unit/services/test_secret_store.py
git commit -m "$(cat <<'EOF'
refactor(secret-store): pin SecretStore.list() to KV v2 LIST semantics

Docstring now specifies that list() returns immediate children (relative
names; sub-directory entries end with `/`, leaves don't). The ConcreteSecretStore
test stub is updated to honor the new contract, and two new tests cover
directory markers and the exact-match-prefix edge case.

InMemorySecretStore (production test backend) is aligned in the next commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Align `InMemorySecretStore.list`

**Files:**
- Modify: `src/lfx/src/lfx/services/secret_store/factory.py`

(No new test file — the ABC tests in Task 1 already cover the contract behavior, and `auto_secrets.py` tests in Task 3 will cover the integration.)

- [ ] **Step 1: Rewrite `InMemorySecretStore.list`**

In `src/lfx/src/lfx/services/secret_store/factory.py` (around lines 28-29), replace:

```python
async def list(self, prefix: str) -> list[str]:
    return [k for k in self._store if k.startswith(prefix)]
```

with:

```python
async def list(self, prefix: str) -> list[str]:
    seen: set[str] = set()
    for key in self._store:
        if not key.startswith(prefix):
            continue
        rest = key[len(prefix):]
        if not rest:
            continue
        head, sep, _ = rest.partition("/")
        seen.add(head + ("/" if sep else ""))
    return sorted(seen)
```

- [ ] **Step 2: Run the SecretStore unit tests**

```
uv run pytest src/lfx/tests/unit/services/test_secret_store.py -v
```
Expected: all PASS (no test directly exercises `InMemorySecretStore`; tests use `ConcreteSecretStore` which now mirrors the same shape).

- [ ] **Step 3: Run the autosecret unit tests as a regression check**

```
uv run pytest src/backend/tests/unit/services/variable/test_auto_secrets.py -v
```
Expected: all PASS. The autosecret tests use `InMemorySecretStore` via the cleanup/delete walk through `_list_autosecret_paths`. The helper currently sniffs both contracts, so it still works correctly even though the InMemory shape just changed. (Task 3 deletes the helper.)

If this fails, STOP and investigate — the InMemory rewrite should be drop-in compatible with the existing helper.

- [ ] **Step 4: Commit**

```bash
git add src/lfx/src/lfx/services/secret_store/factory.py
git commit -m "$(cat <<'EOF'
refactor(secret-store): align InMemorySecretStore.list to KV v2 contract

Now returns immediate children (relative names; "/"-suffixed sub-directories,
leaves bare) instead of all absolute keys under prefix. Matches VaultSecretStore
behavior; lets callers code against one shape instead of sniffing both.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Drop the `_list_autosecret_paths` helper

**Files:**
- Modify: `src/backend/base/langflow/services/variable/auto_secrets.py`

- [ ] **Step 1: Run the autosecret tests as a baseline**

```
uv run pytest src/backend/tests/unit/services/variable/test_auto_secrets.py -v
```
Expected: 12 PASS (state after Tasks 1 + 2 of this plan; helper still in place).

- [ ] **Step 2: Delete `_list_autosecret_paths`**

In `src/backend/base/langflow/services/variable/auto_secrets.py`, delete the function `_list_autosecret_paths` (around lines 186-207). It looks like:

```python
async def _list_autosecret_paths(secret_store: SecretStore, base: str) -> list[str]:
    """Walk a Vault-style two-level prefix and return absolute paths.

    Bridges the two SecretStore contracts in play:
      ...
    """
    out: list[str] = []
    for entry in await secret_store.list(base):
        if entry.startswith(base):
            out.append(entry)
        elif entry.endswith("/"):
            out.extend(await _list_autosecret_paths(secret_store, base + entry))
        else:
            out.append(base + entry)
    return out
```

- [ ] **Step 3: Inline the two-level walk in `cleanup_orphaned_autosecrets`**

Replace the body of `cleanup_orphaned_autosecrets` (currently uses `_list_autosecret_paths`) with:

```python
async def cleanup_orphaned_autosecrets(
    *,
    flow_data: dict,
    flow_id: UUID,
    user_id: UUID,
    secret_store: SecretStore,
    session: AsyncSession,
) -> None:
    """Delete Vault autosecrets whose (node_id, field_name) is no longer
    present in the flow's current template."""
    org_id = await _get_org_id_for_flow(flow_id, session=session)
    if org_id is None:
        return

    base = f"{org_id}/flows/{flow_id}/autosecrets/"
    existing: set[tuple[str, str]] = set()
    for node_entry in await secret_store.list(base):
        if not node_entry.endswith("/"):
            # Defensive: leaf at node-id depth shouldn't exist; skip.
            continue
        node_id = node_entry.rstrip("/")
        for field_entry in await secret_store.list(f"{base}{node_id}/"):
            if field_entry.endswith("/"):
                # Defensive: sub-dir at field-name depth shouldn't exist; skip.
                continue
            existing.add((node_id, field_entry))

    current = {(node_id, field_name) for node_id, field_name, _ in _iter_promotable_fields(flow_data)}

    for node_id, field_name in existing - current:
        await secret_store.delete(f"{base}{node_id}/{field_name}")
```

- [ ] **Step 4: Inline the two-level walk in `delete_autosecrets_for_flow`**

Replace its body with:

```python
async def delete_autosecrets_for_flow(
    *,
    flow_id: UUID,
    user_id: UUID,
    secret_store: SecretStore,
    session: AsyncSession,
) -> None:
    """Delete every Vault autosecret owned by this flow. Call on flow delete."""
    org_id = await _get_org_id_for_flow(flow_id, session=session)
    if org_id is None:
        return

    base = f"{org_id}/flows/{flow_id}/autosecrets/"
    for node_entry in await secret_store.list(base):
        if not node_entry.endswith("/"):
            continue
        node_id = node_entry.rstrip("/")
        for field_entry in await secret_store.list(f"{base}{node_id}/"):
            if field_entry.endswith("/"):
                continue
            await secret_store.delete(f"{base}{node_id}/{field_entry}")
```

- [ ] **Step 5: Run the autosecret tests**

```
uv run pytest src/backend/tests/unit/services/variable/test_auto_secrets.py -v
```
Expected: 12 PASS (same count as the baseline). External behavior is unchanged; only the internal walk shape changed.

- [ ] **Step 6: Run the broader variable-service unit suite**

```
uv run pytest src/backend/tests/unit/services/variable -v
```
Expected: all PASS for the migration-related files. The 14 pre-existing failures in `test_service.py` (organization_id NOT NULL) remain unrelated.

- [ ] **Step 7: Run the real-Vault integration test if Vault is available locally**

Optional, only if you have a Vault dev container handy:

```
VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=devroot \
  uv run pytest src/backend/tests/integration/services/test_autosecrets_vault.py -v
```
Expected: 2 PASS. (Skipped if no Vault env.)

- [ ] **Step 8: Commit**

```bash
git add src/backend/base/langflow/services/variable/auto_secrets.py
git commit -m "$(cat <<'EOF'
refactor(autosecrets): drop _list_autosecret_paths workaround

InMemorySecretStore now matches Vault's KV v2 LIST contract, so the
backend-sniffing helper is unnecessary. cleanup_orphaned_autosecrets and
delete_autosecrets_for_flow now do an explicit two-level walk
(node_id directories → field_name leaves), with defensive skips for any
unexpected nesting at either depth.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final verification

- [ ] Full SecretStore unit suite green:
  ```
  uv run pytest src/lfx/tests/unit/services/test_secret_store.py -v
  ```

- [ ] Full autosecrets unit suite green:
  ```
  uv run pytest src/backend/tests/unit/services/variable/test_auto_secrets.py -v
  ```

- [ ] (Optional) Real-Vault integration tests green if Vault is available.

- [ ] `git log --oneline -5` shows three focused commits, no `git add -A` collateral.

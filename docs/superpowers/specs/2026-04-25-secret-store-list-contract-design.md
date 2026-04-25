# SecretStore.list() Contract Alignment

**Status:** Design complete
**Date:** 2026-04-25
**Branch:** `platform-multi-tenant`

## Goal

Pin the `SecretStore.list()` contract to Vault KV v2 LIST semantics (return immediate children only; sub-directory entries end with `/`, leaf entries don't). Align `InMemorySecretStore.list()` to match, and drop the `_list_autosecret_paths` workaround that currently bridges the two divergent behaviors.

## Background

The autosecrets→Vault migration (commits `f1d6353683` … `366fe8f366`) introduced one consumer of `SecretStore.list()`: a two-level walk under `{org_id}/flows/{flow_id}/autosecrets/` for cleanup and delete operations. While implementing T5 of that migration, the engineer discovered the two backends return different shapes:

- **`InMemorySecretStore.list(prefix)`** — `[k for k in self._store if k.startswith(prefix)]` (all absolute keys, recursive).
- **`VaultSecretStore.list(prefix)`** — KV v2 `list_secrets` returns immediate-children names; sub-directory entries end with `/`.

A defensive helper `_list_autosecret_paths` was added to `auto_secrets.py` that sniffs both shapes (absolute vs relative) and produces correct delete calls. The reviewer flagged this as a workaround papering over an ABC-level abstraction gap.

The fix lives at the contract layer, not in `auto_secrets.py`. Vault's behavior is authoritative — it matches the well-known KV v2 LIST idiom and is what real callers will encounter in production.

## Scope

**In scope:**
- ABC docstring in `base.py` pinned to the KV v2 idiom.
- `InMemorySecretStore.list` rewritten to return immediate children with `/`-suffix for sub-directories.
- `_list_autosecret_paths` helper deleted from `auto_secrets.py`; its two callers (`cleanup_orphaned_autosecrets`, `delete_autosecrets_for_flow`) inline an explicit two-level walk.
- `test_secret_store.py` assertions updated to match the new InMemory contract.

**Out of scope:**
- `VaultSecretStore.list` — already correct, no change.
- Any `list_recursive(prefix)` sibling method on the ABC (no second consumer to justify it; YAGNI).
- User-managed Variable migration to Vault.
- Behavior changes to other `SecretStore` methods (`get`, `put`, `delete`).

## Architecture

The `SecretStore` ABC is the contract; both backends honor it. Today the ABC docstring is silent on the shape of `list()`'s return. We pin it. Both backends and the autosecret caller align around one rule.

```
                ┌─────────────────────────────┐
                │  SecretStore.list(prefix)   │
                │  → list[str]                │
                │                              │
                │  Returns immediate children. │
                │  Sub-dirs end with "/".      │
                │  Leaves do not.              │
                └──────────────┬───────────────┘
                               │
              ┌────────────────┴────────────────┐
              ▼                                  ▼
    ┌───────────────────┐              ┌───────────────────┐
    │ VaultSecretStore  │              │ InMemorySecretStore│
    │ (unchanged —      │              │ (rewrite to match) │
    │  already correct) │              │                    │
    └───────────────────┘              └───────────────────┘
                               │
                               ▼
              auto_secrets.py: explicit two-level walk
              (no helper, no contract sniffing)
```

## Contract

```python
class SecretStore(ABC):
    @abstractmethod
    async def list(self, prefix: str) -> list[str]:
        """List immediate children under a prefix (KV v2 LIST semantics).

        Returns relative names — sub-directory entries end with `/`, leaf
        entries do not. Callers walking deeper structure must recurse explicitly.

        Example:
            store has keys: ["a/b/c", "a/b/d", "a/e"]
            store.list("a/")  → ["b/", "e"]
            store.list("a/b/") → ["c", "d"]
        """
```

`prefix` is matched verbatim — no normalization. Callers include trailing `/` when they want directory-style listing.

## Implementation

### `InMemorySecretStore.list` (rewrite)

```python
async def list(self, prefix: str) -> list[str]:
    seen: set[str] = set()
    for key in self._store:
        if not key.startswith(prefix):
            continue
        rest = key[len(prefix):]
        if not rest:
            continue  # exact-match (key == prefix); not a child
        head, sep, _ = rest.partition("/")
        seen.add(head + ("/" if sep else ""))
    return sorted(seen)
```

`sorted()` keeps test output deterministic. The `if not rest` guard handles the edge where a key equals the prefix exactly (not a child).

### `auto_secrets.py` — drop helper, inline walks

Delete `_list_autosecret_paths` (~lines 186-207).

`cleanup_orphaned_autosecrets` body (after the org-id null-check) becomes:

```python
base = f"{org_id}/flows/{flow_id}/autosecrets/"
existing: set[tuple[str, str]] = set()
for node_entry in await secret_store.list(base):
    if not node_entry.endswith("/"):
        # Defensive: leaf at node-id depth shouldn't happen. Skip.
        continue
    node_id = node_entry.rstrip("/")
    for field_entry in await secret_store.list(f"{base}{node_id}/"):
        if field_entry.endswith("/"):
            # Defensive: sub-dir at field-name depth shouldn't happen. Skip.
            continue
        existing.add((node_id, field_entry))

current = {(n, f) for n, f, _ in _iter_promotable_fields(flow_data)}
for node_id, field_name in existing - current:
    await secret_store.delete(f"{base}{node_id}/{field_name}")
```

`delete_autosecrets_for_flow` mirrors the walk and just deletes every reached leaf:

```python
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

The defensive `continue` branches are cheap and keep the code resilient against any future stray nesting (e.g., a manual Vault edit creating an unexpected sub-directory).

## Tests

### Existing `test_secret_store.py` updates

Find tests that assert against `list()` output. Update assertions to match the new contract:

- A test that builds keys `["a/b", "a/c"]` and asserts `list("a/") == ["a/b", "a/c"]` (absolute) becomes `list("a/") == ["b", "c"]` (relative).
- Add a new test covering directory-marker behavior: keys `["a/b/c", "a/d"]`, assert `list("a/") == ["b/", "d"]`.
- Add a test for the exact-match-prefix edge: a key equal to the prefix should not appear in `list(prefix)`.

### Existing `test_auto_secrets.py`

Should pass unchanged. The cleanup/delete tests don't call `.list` directly; they exercise `cleanup_orphaned_autosecrets` / `delete_autosecrets_for_flow` and assert on Vault state via `.get`. With both the InMemory backend and the auto_secrets walk updated together, external behavior is identical.

### Real-Vault integration tests (`test_autosecrets_vault.py`)

Should pass unchanged. They've always exercised the Vault contract; this refactor just brings InMemory into agreement.

## Files touched

| File | Status | Why |
|---|---|---|
| `src/lfx/src/lfx/services/secret_store/base.py` | Modify | Pin docstring to KV v2 idiom. |
| `src/lfx/src/lfx/services/secret_store/factory.py` | Modify | `InMemorySecretStore.list` rewrite. |
| `src/backend/base/langflow/services/variable/auto_secrets.py` | Modify | Delete `_list_autosecret_paths`; inline two-level walks. |
| `src/lfx/tests/unit/services/test_secret_store.py` | Modify | Update list-contract assertions; add directory-marker test. |

`VaultSecretStore` is unchanged. Existing autosecret unit tests are unchanged. Existing autosecret integration tests are unchanged.

## Out of scope / follow-ups

- `list_recursive(prefix)` if a future caller needs the all-paths-under-prefix shape.
- Pagination semantics (KV v2 list returns a single response; not a concern for our scale).
- Any other shape divergence between InMemory and Vault implementations of other methods (none currently known).

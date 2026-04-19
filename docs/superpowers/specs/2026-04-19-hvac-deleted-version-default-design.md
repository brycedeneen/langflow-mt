# Adopt hvac v3's `raise_on_deleted_version=False` default in VaultSecretStore

## Problem

Running tests emits:

```
DeprecationWarning: The raise_on_deleted_version parameter will change its
default value to False in hvac v3.0.0. The current default of True will
preserve previous behavior. To use the old behavior with no warning, explicitly
set this value to True. See https://github.com/hvac/hvac/pull/907
```

Source: `src/lfx/src/lfx/services/secret_store/vault.py:26` — `VaultSecretStore.get()` calls `read_secret_version` without passing `raise_on_deleted_version`, inheriting hvac 2.x's soon-to-flip default.

hvac 3.0.0 is not yet published (latest on PyPI is 2.4.0), so a dependency-cap bump is not possible today. The goal is to silence the warning *and* make the call forward-compatible with v3, so when v3 ships the only remaining work is a cap bump plus a changelog review.

## Decision

Set `raise_on_deleted_version=False` explicitly at the call site and fold soft-deleted versions into the existing "not found" contract of `SecretStore.get()`.

Rationale:

- Callers of `get()` already treat `None` as "not present." A soft-deleted latest version is operationally indistinguishable from a missing secret — they should behave the same way.
- Raising a version-specific error is not useful here: the current code only catches `InvalidPath`, so a deleted-version error would propagate as an unhandled exception. Silently masking it by catching more broadly would be worse than returning `None`.
- Aligning with v3's default now means zero code change at the call site when the cap is eventually raised.

## Scope

**In scope**

- `src/lfx/src/lfx/services/secret_store/vault.py` — add the kwarg, handle the deleted-version response shape.
- `src/lfx/tests/unit/services/test_secret_store.py` — update expectations, add one coverage test for the deleted-version path.

**Out of scope**

- Bumping the `hvac` version cap. Blocked on v3 release and changelog review. Track as a separate follow-up.
- Changing `put()`, `delete()`, or `list()`. They don't hit the deprecated default.
- Any `SecretStore` interface changes. The `get() -> dict | None` contract is unchanged.

## Implementation

### `VaultSecretStore.get`

```python
async def get(self, path: str) -> dict | None:
    try:
        response = await asyncio.to_thread(
            self._client.secrets.kv.v2.read_secret_version,
            path=path,
            mount_point=self._mount_point,
            raise_on_deleted_version=False,
        )
    except InvalidPath:
        return None
    return (response.get("data") or {}).get("data")
```

Notes:

- `InvalidPath` still covers the "path never existed / tombstone purged" case — hvac raises this regardless of the flag.
- When the latest version is soft-deleted, hvac returns a response whose `data.data` is `None` (and `data.metadata.deletion_time` is set). The `.get()` chain collapses that to `None`.
- Using `.get()` rather than `response["data"]["data"]` avoids a `KeyError` on the deleted-version shape while still returning the dict payload on the happy path.

### Tests

Update `test_secret_store.py`:

1. **Happy path** (existing): update the mock-call assertion to include `raise_on_deleted_version=False` so the fix is pinned by a test.
2. **Missing path** (existing `InvalidPath` test): no change.
3. **New: soft-deleted latest version.** Mock `read_secret_version` to return `{"data": {"data": None, "metadata": {"deletion_time": "2026-04-19T00:00:00Z"}}}` and assert `await store.get(path) is None`.

No new integration tests — unit coverage against a mocked hvac client is sufficient for a call-site change of this size.

## Risks

- **Shape assumption.** The spec assumes `data.data is None` for soft-deleted versions. This matches hvac's documented behavior and the Vault KV v2 API, but the new unit test pins the assumption so a regression would fail fast.
- **Warning source confirmation.** The pytest config uses `--disable-warnings`, but the warning still appears when other runners (e.g., the repo-level venv with `LFX_TEST_ALLOW_LANGFLOW=1`) surface warnings. Fixing the call site resolves it at the source.

## Follow-up (not part of this spec)

When hvac 3.0.0 ships:

1. Read the v3 changelog for other breaking changes (exception hierarchy, response shapes, auth backends).
2. Run `src/lfx` tests against the new version locally.
3. Bump the cap in `src/lfx/pyproject.toml` from `<3.0.0` to `<4.0.0`.
4. `uv.lock` regeneration.

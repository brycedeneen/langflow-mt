# hvac deleted-version default — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **User git rule (from auto-memory):** Do NOT run `git commit` without explicit user confirmation, even when a step below says to commit. Pause, print the diff summary, and ask first.

**Goal:** Silence the `raise_on_deleted_version` deprecation warning from hvac by explicitly adopting v3's future default (`False`) at the `VaultSecretStore.get()` call site, so soft-deleted Vault secrets collapse to the existing "not found" contract.

**Architecture:** Single call-site change in `VaultSecretStore.get()` — pass `raise_on_deleted_version=False` and harden the response-dict access so the soft-deleted response shape (`data.data is None`) returns `None` to callers. Two unit-test updates pin the new behavior. No dependency bump; `hvac>=2.0.0,<3.0.0` stays.

**Tech Stack:** Python 3.12, pytest + pytest-asyncio, `hvac` 2.x (synchronous client wrapped in `asyncio.to_thread`), `unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-04-19-hvac-deleted-version-default-design.md`

---

## File Structure

**Modify**

- `src/lfx/src/lfx/services/secret_store/vault.py` — add the kwarg to `read_secret_version`, switch to `.get()`-chained response access.
- `src/lfx/tests/unit/services/test_secret_store.py` — tighten the happy-path assertion to pin the new kwarg; add one test for the soft-deleted response shape.

No new files.

---

## Test Runner Notes

Tests live under `src/lfx/tests/`. Per the `LFX_TEST_ALLOW_LANGFLOW` auto-memory note, when running from the repo-level venv you must export `LFX_TEST_ALLOW_LANGFLOW=1` or the tests will skip/opt out.

Commands used below assume you're at the repo root:

```bash
export LFX_TEST_ALLOW_LANGFLOW=1
uv run --directory src/lfx pytest tests/unit/services/test_secret_store.py -v
```

If that invocation doesn't work in your shell, fall back to:

```bash
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/services/test_secret_store.py -v
```

---

## Task 1: Pin the new kwarg with a failing test, then fix `get()`

**Files:**
- Modify: `src/lfx/tests/unit/services/test_secret_store.py:117-125` (`test_get_returns_data`)
- Modify: `src/lfx/src/lfx/services/secret_store/vault.py:23-32` (`VaultSecretStore.get`)

- [ ] **Step 1: Tighten the happy-path test to assert the new kwarg is passed**

Replace `test_get_returns_data` in `src/lfx/tests/unit/services/test_secret_store.py` with:

```python
    @pytest.mark.asyncio
    async def test_get_returns_data(self):
        store = self._make_store()
        mock_response = {"data": {"data": {"api_key": "ADP-APICPRO-abc123"}}}
        with patch.object(
            store._client.secrets.kv.v2, "read_secret_version", return_value=mock_response
        ) as mock_read:
            result = await store.get("org1/webhooks/flow1")
            assert result == {"api_key": "ADP-APICPRO-abc123"}
            mock_read.assert_called_once_with(
                path="org1/webhooks/flow1",
                mount_point="secret",
                raise_on_deleted_version=False,
            )
```

- [ ] **Step 2: Run the test and confirm it fails on the kwarg assertion**

```bash
export LFX_TEST_ALLOW_LANGFLOW=1
uv run --directory src/lfx pytest tests/unit/services/test_secret_store.py::TestVaultSecretStore::test_get_returns_data -v
```

Expected: `FAILED` — the `assert_called_once_with` fails because the real call is missing `raise_on_deleted_version=False`. The result equality still passes.

- [ ] **Step 3: Update `VaultSecretStore.get` to pass the kwarg and tolerate the deleted-version shape**

In `src/lfx/src/lfx/services/secret_store/vault.py`, replace the existing `get` method:

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

Notes for the implementer:
- The `InvalidPath` branch still handles paths that never existed (hvac raises this regardless of the flag).
- `(response.get("data") or {}).get("data")` returns `None` both when `data.data is None` (soft-deleted latest version) and when the key is missing. `response["data"]["data"]` would `KeyError` on a malformed response; the chained `.get()` is safer without changing the happy-path contract.

- [ ] **Step 4: Rerun the same test and confirm it passes**

```bash
uv run --directory src/lfx pytest tests/unit/services/test_secret_store.py::TestVaultSecretStore::test_get_returns_data -v
```

Expected: `PASSED`.

- [ ] **Step 5: Run the full `TestVaultSecretStore` class to confirm no regressions**

```bash
uv run --directory src/lfx pytest tests/unit/services/test_secret_store.py::TestVaultSecretStore -v
```

Expected: 7 tests pass (`test_put_calls_vault_create_or_update`, `test_get_returns_data`, `test_get_nonexistent_returns_none`, `test_delete_calls_vault_delete`, `test_delete_nonexistent_is_noop`, `test_list_returns_keys`, `test_list_empty_returns_empty`).

- [ ] **Step 6: Ask the user before committing, then commit**

Pause and ask the user to confirm the commit. After confirmation:

```bash
git add src/lfx/src/lfx/services/secret_store/vault.py src/lfx/tests/unit/services/test_secret_store.py
git commit -m "fix(secret-store): adopt hvac v3's raise_on_deleted_version=False default

Silences the hvac DeprecationWarning and makes VaultSecretStore.get()
forward-compatible with the eventual hvac v3 bump. Soft-deleted latest
versions now collapse to None, matching the existing not-found contract."
```

---

## Task 2: Add coverage for the soft-deleted response shape

**Files:**
- Modify: `src/lfx/tests/unit/services/test_secret_store.py` (add one method to `TestVaultSecretStore`, just after `test_get_nonexistent_returns_none` at line 137)

- [ ] **Step 1: Add the deleted-version test**

Insert this method into `TestVaultSecretStore`, immediately after `test_get_nonexistent_returns_none`:

```python
    @pytest.mark.asyncio
    async def test_get_soft_deleted_version_returns_none(self):
        store = self._make_store()
        mock_response = {
            "data": {
                "data": None,
                "metadata": {"deletion_time": "2026-04-19T00:00:00Z"},
            }
        }
        with patch.object(
            store._client.secrets.kv.v2, "read_secret_version", return_value=mock_response
        ):
            result = await store.get("org1/webhooks/flow1")
            assert result is None
```

- [ ] **Step 2: Run the new test**

```bash
uv run --directory src/lfx pytest tests/unit/services/test_secret_store.py::TestVaultSecretStore::test_get_soft_deleted_version_returns_none -v
```

Expected: `PASSED` — after Task 1's code change, the chained `.get()` correctly returns `None` for the deleted-version shape. (The test is pinning the contract rather than driving a code change, but still valuable because a future refactor that reverts to `response["data"]["data"]` would now `TypeError` against this fixture and fail here.)

- [ ] **Step 3: Run the full test file one more time**

```bash
uv run --directory src/lfx pytest tests/unit/services/test_secret_store.py -v
```

Expected: all previously-passing tests still pass, plus the new one. Total should be one more than before.

- [ ] **Step 4: Ask the user before committing, then commit**

Pause and ask. After confirmation:

```bash
git add src/lfx/tests/unit/services/test_secret_store.py
git commit -m "test(secret-store): cover soft-deleted Vault version returning None"
```

---

## Task 3: Verify the deprecation warning is gone at the source

**Files:** none modified — this task is verification only.

- [ ] **Step 1: Confirm the warning is not emitted by the targeted test**

The lfx `pyproject.toml` sets `--disable-warnings` in `addopts`, which silences warnings in the summary but does not suppress the emission itself. To verify the warning is gone at the source, run the test with pytest's `-W error` override, which turns any emitted DeprecationWarning into a test failure:

```bash
uv run --directory src/lfx pytest \
  tests/unit/services/test_secret_store.py::TestVaultSecretStore::test_get_returns_data \
  -v -W "error::DeprecationWarning"
```

Expected: `PASSED`. If the warning still emitted, pytest would convert it to an error and the test would fail with a traceback pointing at `concurrent/futures/thread.py` and the hvac message.

- [ ] **Step 2: Spot-check the same invocation across the full VaultSecretStore suite**

```bash
uv run --directory src/lfx pytest \
  tests/unit/services/test_secret_store.py::TestVaultSecretStore \
  -v -W "error::DeprecationWarning"
```

Expected: all 8 tests (7 pre-existing + the new one from Task 2) pass with no DeprecationWarning-driven failures.

- [ ] **Step 3: No commit for this task.**

It's verification-only. If Steps 1–2 pass, the feature is complete.

---

## Definition of Done

- `VaultSecretStore.get()` passes `raise_on_deleted_version=False` explicitly.
- `src/lfx/tests/unit/services/test_secret_store.py::TestVaultSecretStore` passes in full (8 tests).
- `pytest -W error::DeprecationWarning` on the same suite passes — no hvac deprecation warning is emitted.
- `hvac` version cap in `src/lfx/pyproject.toml` is **unchanged** at `>=2.0.0,<3.0.0`. (The v3 bump is explicitly a follow-up, gated on v3 being published.)

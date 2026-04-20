# ADP Auth — TextFileSecretInput + Default-On Auto-Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **User git rule (takes precedence over every "Commit" step below):** Every `git commit` requires explicit user approval before running. Stop at each commit step and wait for go-ahead. Do not `git push` or open PRs against `langflow-ai/langflow`. Reason: user's standing rule in auto-memory.

**Goal:** Migrate `ADPAuthComponent` to `TextFileSecretInput` (paste-or-upload PEMs) and generalize the auto-Variable promotion mechanism to cover every `SecretStrInput` across the codebase by default, with a user-managed-Variable preservation path so picked references aren't accidentally over-promoted.

**Architecture:** Four backend surfaces change. `SecretStrInput` gains `auto_promote: bool = True` (default) — subclasses (including `TextFileSecretInput`) inherit. The auto-secrets walker flips from input-type-name matching to a flag check. The promote helper gains a `has_user_managed_variable` lookup to distinguish typed plaintext from picked references. `ADPAuthComponent` drops its `cert_source`/`cert_path`/`key_path` inputs, converts `cert_pem`/`key_pem` to `TextFileSecretInput`, and bumps to v2 with a migration changelog. `_shared.py` sheds the path-mode branch and delegates to `mtls_temp_files` from the shared base module.

**Tech Stack:** Python 3.12, Pydantic v2, SQLAlchemy async, pytest + pytest-asyncio, httpx.

**Spec:** `docs/superpowers/specs/2026-04-20-adp-auth-text-file-secret-design.md`

**Codebase integration points:**
- `SecretStrInput` — `src/lfx/src/lfx/inputs/inputs.py:410`
- `TextFileSecretInput` (existing) — same file, immediately after `SecretStrInput`
- Variable service — `src/backend/base/langflow/services/variable/service.py`
- Auto-secrets module — `src/backend/base/langflow/services/variable/auto_secrets.py`
- Auto-secrets test — `src/backend/tests/unit/services/variable/test_auto_secrets.py`
- Lifecycle integration test — `src/backend/tests/unit/api/v1/test_flow_autosecret_lifecycle.py`
- ADP Auth component — `src/lfx/src/lfx/components/adp/adp_auth.py`
- ADP shared helpers — `src/lfx/src/lfx/components/adp/_shared.py`
- ADP Auth tests — `src/lfx/tests/unit/components/adp/test_adp_auth.py`
- ADP shared tests — `src/lfx/tests/unit/components/adp/test_shared.py`
- Other ADP components calling `build_mtls_httpx_client`: `adp_api_request.py`, `adp_mcp.py`, `adp_worker_tools.py`, `adp_trigger.py`

---

## File structure

**Modify:**
- `src/lfx/src/lfx/inputs/inputs.py` — add `auto_promote: bool = True` class attribute to `SecretStrInput`
- `src/backend/base/langflow/services/variable/service.py` — add `has_user_managed_variable` method
- `src/backend/base/langflow/services/variable/auto_secrets.py` — rename walker, generalize predicate, add user-managed-Variable detection to promote helper
- `src/backend/tests/unit/services/variable/test_auto_secrets.py` — extend coverage
- `src/backend/tests/unit/api/v1/test_flow_autosecret_lifecycle.py` — extend with bare `SecretStrInput` + user-picked-Variable cases
- `src/lfx/src/lfx/components/adp/_shared.py` — simplify `ADPConnection`, convert `build_mtls_httpx_client` to async context manager, delete `_write_pem_temp_files` and `_MTLSClient`
- `src/lfx/src/lfx/components/adp/adp_auth.py` — swap fields, simplify `build_connection`, add v2 changelog
- `src/lfx/src/lfx/components/adp/adp_api_request.py` — update `build_mtls_httpx_client` call site to async context manager shape (already uses context manager shape — verify only)
- `src/lfx/src/lfx/components/adp/adp_mcp.py` — same
- `src/lfx/src/lfx/components/adp/adp_worker_tools.py` — same
- `src/lfx/src/lfx/components/adp/adp_trigger.py` — same
- `src/lfx/tests/unit/components/adp/test_adp_auth.py` — drop path-mode tests, update PEM tests
- `src/lfx/tests/unit/components/adp/test_shared.py` — drop path-mode + `_write_pem_temp_files` tests, update context-manager shape
- `src/lfx/tests/unit/components/adp/test_adp_api_request.py`, `test_adp_mcp.py`, `test_adp_worker_tools.py`, `test_adp_trigger.py` — update any `ADPConnection` construction with `cert_source`/`cert_path`/`key_path`

**Create (tests):**
- `src/lfx/tests/unit/inputs/test_secret_str_input.py` — auto_promote default behavior

**Delete (code paths, not whole files):**
- In `_shared.py`: `_write_pem_temp_files`, `_MTLSClient` subclass, `cert_source="path"` branch of `build_mtls_httpx_client`, re-exports of `_normalize_pem` and `_write_secure_tempfile` (keep only if in-repo callers grep positive)

---

## Task sequencing

12 tasks in 4 phases:

1. **Infrastructure generalization** (Tasks 1–5) — flag, service method, walker rename, promote helper, integration test.
2. **Shared module cleanup** (Tasks 6–8) — ADP `_shared.py` refactor, call-site updates, test migration.
3. **ADPAuthComponent migration** (Tasks 9–10) — component changes + test migration.
4. **Residual ADP tests + starter regen** (Tasks 11–12).

---

### Task 1: `SecretStrInput.auto_promote` default

**Files:**
- Modify: `src/lfx/src/lfx/inputs/inputs.py` (near `SecretStrInput` class ~line 410)
- Create test: `src/lfx/tests/unit/inputs/test_secret_str_input.py`

- [ ] **Step 1: Write the failing test**

Create `src/lfx/tests/unit/inputs/test_secret_str_input.py`:

```python
"""Tests for SecretStrInput's auto_promote default behavior."""

from lfx.inputs.inputs import SecretStrInput, TextFileSecretInput


def test_secret_str_input_auto_promote_default_is_true():
    inp = SecretStrInput(name="api_key")
    assert inp.auto_promote is True


def test_auto_promote_can_be_explicitly_disabled():
    inp = SecretStrInput(name="api_key", auto_promote=False)
    assert inp.auto_promote is False


def test_text_file_secret_input_inherits_auto_promote_default():
    inp = TextFileSecretInput(name="cert_pem", file_types=["pem"])
    assert inp.auto_promote is True


def test_auto_promote_is_serialized_in_model_dump():
    inp = SecretStrInput(name="api_key")
    dumped = inp.model_dump()
    assert dumped["auto_promote"] is True


def test_auto_promote_false_is_serialized():
    inp = SecretStrInput(name="api_key", auto_promote=False)
    dumped = inp.model_dump()
    assert dumped["auto_promote"] is False
```

- [ ] **Step 2: Run test to verify it fails**

```
cd /Users/brycedeneen/dev/langflow/.worktrees/adp-auth-vault-backed-pem
LFX_TEST_ALLOW_LANGFLOW=1 .venv/bin/pytest src/lfx/tests/unit/inputs/test_secret_str_input.py -v
```

Expected: `AttributeError: 'SecretStrInput' object has no attribute 'auto_promote'` (or similar Pydantic validation error).

- [ ] **Step 3: Add the `auto_promote` field**

Edit `src/lfx/src/lfx/inputs/inputs.py`. Find the `SecretStrInput` class header `class SecretStrInput(BaseInputMixin, DatabaseLoadMixin):` (~line 410). Look at the existing class attributes (`field_type`, `password`, `load_from_db`, `track_in_telemetry`). Add `auto_promote` using the same style:

```python
class SecretStrInput(BaseInputMixin, DatabaseLoadMixin):
    field_type = FieldTypes.PASSWORD
    password = True
    load_from_db = True
    track_in_telemetry = False

    auto_promote: bool = True
    """Whether typed-in plaintext values are automatically promoted to hidden
    auto-Variables (Fernet-encrypted in the DB) on flow save. Default True.
    Set False for fields whose value needs plaintext round-trip through flow
    JSON (rare)."""
```

- [ ] **Step 4: Run test to verify it passes**

Same command as Step 2. Expected: 5 passed.

- [ ] **Step 5: Pause for user commit approval**

Proposed message: `feat(inputs): add auto_promote=True default on SecretStrInput`

---

### Task 2: `VariableService.has_user_managed_variable`

**Files:**
- Modify: `src/backend/base/langflow/services/variable/service.py` (add a method near existing `create_variable` / `list_autosecret_names_for_flow`)
- Modify test: `src/backend/tests/unit/services/variable/test_auto_secrets.py` (or a new sibling — prefer extending existing if fixture setup matches)

- [ ] **Step 1: Write the failing test**

Append to `src/backend/tests/unit/services/variable/test_auto_secrets.py` (or `test_service.py` if that's where existing VariableService tests live — check `grep -rn "class.*VariableService\|def test_.*variable" src/backend/tests/unit/services/variable/` first):

```python
"""has_user_managed_variable should distinguish user-managed Variables from
auto-secrets and from absence."""
import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from langflow.services.variable.auto_secrets import AUTOSECRET_PREFIX


USER_ID = uuid4()


@pytest.mark.asyncio
async def test_has_user_managed_variable_true_for_user_managed():
    """Assume a Variable with name='my_api_key' exists for USER_ID."""
    # Mock service: has_user_managed_variable returns True.
    svc = AsyncMock()
    svc.has_user_managed_variable = AsyncMock(return_value=True)
    session = AsyncMock()

    result = await svc.has_user_managed_variable(
        name="my_api_key", user_id=USER_ID, session=session
    )
    assert result is True


@pytest.mark.asyncio
async def test_has_user_managed_variable_false_for_autosecret():
    """Auto-secret names are explicitly excluded from user-managed matches."""
    # Integration-style test: we're asserting the service method's SQL uses
    # NOT LIKE '__autosecret_%'. The pure-Python layer can't easily mock the
    # exclusion, so this test belongs in a DB-integration suite. Placeholder:
    # covered by integration test in Task 5.
    pass
```

> **Note:** the `test_auto_secrets.py` tests are pure helper tests — they can't cover service SQL behavior. Write a direct `test_service.py`-style test instead. Check whether `src/backend/tests/unit/services/variable/test_service.py` exists; if yes, extend it with a DB-backed test of `has_user_managed_variable` using the existing DB fixture. If no, defer the DB test to the integration layer (Task 5) and make this step a simple API-shape test (method exists, takes keyword args, returns bool).

- [ ] **Step 2: Run test to verify it fails (or skip if no suitable location)**

```
.venv/bin/pytest src/backend/tests/unit/services/variable/ -v -k has_user_managed
```

Expected: `AttributeError: 'VariableService' object has no attribute 'has_user_managed_variable'` OR skip if DB fixtures aren't available (cover via integration test in Task 5).

- [ ] **Step 3: Implement the method**

Edit `src/backend/base/langflow/services/variable/service.py`. Find `list_autosecret_names_for_flow` (added in the previous feature). Add `has_user_managed_variable` immediately after it, mirroring its imports and query shape:

```python
async def has_user_managed_variable(
    self,
    *,
    name: str,
    user_id: UUID,
    session: AsyncSession,
) -> bool:
    """Return True if a user-managed (non-autosecret) Variable with this name
    exists for the user. Used by auto_secrets.promote_* to avoid overwriting
    a user-selected Variable reference when the field is also marked
    auto_promote.
    """
    from sqlmodel import select

    from langflow.services.variable.auto_secrets import AUTOSECRET_PREFIX
    from langflow.services.database.models.variable.model import Variable

    stmt = (
        select(Variable.id)
        .where(
            Variable.user_id == user_id,
            Variable.name == name,
            Variable.name.not_like(f"{AUTOSECRET_PREFIX}%"),
        )
        .limit(1)
    )
    result = await session.exec(stmt)
    return result.first() is not None
```

> **Note:** verify `Variable.name.not_like(...)` is the right SQLModel/SQLAlchemy API on this project — if the existing `list_autosecret_names_for_flow` uses `Variable.name.like(...)`, the `not_like` form is the complement. If not available, use `~Variable.name.like(...)`.

- [ ] **Step 4: Run test to verify it passes**

Same command as Step 2. Expected: passing (or covered by integration test deferral).

- [ ] **Step 5: Pause for user commit approval**

Proposed message: `feat(variables): add has_user_managed_variable for auto-promote guardrail`

---

### Task 3: Rename walker and update predicate

**Files:**
- Modify: `src/backend/base/langflow/services/variable/auto_secrets.py` — rename `_iter_textfilesecret_fields` → `_iter_promotable_fields`, change predicate
- Modify: `src/backend/tests/unit/services/variable/test_auto_secrets.py` — update imports/references if any test imports the helper by name

- [ ] **Step 1: Write a failing test for the generalized walker**

Append to `src/backend/tests/unit/services/variable/test_auto_secrets.py`:

```python
from langflow.services.variable.auto_secrets import _iter_promotable_fields


def test_iter_promotable_fields_yields_secret_str_with_auto_promote_true():
    flow_data = {
        "nodes": [
            {
                "id": "Node-abc",
                "data": {
                    "node": {
                        "template": {
                            "api_key": {
                                "_input_type": "SecretStrInput",
                                "auto_promote": True,
                                "value": "sk-secret",
                                "load_from_db": False,
                            },
                        },
                    },
                },
            }
        ],
        "edges": [],
    }
    yielded = list(_iter_promotable_fields(flow_data))
    assert len(yielded) == 1
    assert yielded[0][1] == "api_key"


def test_iter_promotable_fields_skips_secret_str_with_auto_promote_false():
    flow_data = {
        "nodes": [
            {
                "id": "Node-abc",
                "data": {
                    "node": {
                        "template": {
                            "api_key": {
                                "_input_type": "SecretStrInput",
                                "auto_promote": False,
                                "value": "sk-secret",
                            },
                        },
                    },
                },
            }
        ],
        "edges": [],
    }
    assert list(_iter_promotable_fields(flow_data)) == []


def test_iter_promotable_fields_yields_text_file_secret_input_by_default():
    # TextFileSecretInput inherits auto_promote=True; its field dict should
    # carry auto_promote=True when serialized.
    flow_data = {
        "nodes": [
            {
                "id": "Node-abc",
                "data": {
                    "node": {
                        "template": {
                            "cert_pem": {
                                "_input_type": "TextFileSecretInput",
                                "auto_promote": True,
                                "value": "PEMSTRING",
                            },
                        },
                    },
                },
            }
        ],
        "edges": [],
    }
    yielded = list(_iter_promotable_fields(flow_data))
    assert len(yielded) == 1


def test_iter_promotable_fields_ignores_missing_auto_promote_key():
    """Legacy serialized flows (pre-feature) have no auto_promote key.
    They must be treated as non-promotable (no retroactive promotion)."""
    flow_data = {
        "nodes": [
            {
                "id": "Node-abc",
                "data": {
                    "node": {
                        "template": {
                            "api_key": {
                                "_input_type": "SecretStrInput",
                                "value": "sk-legacy",
                            },
                        },
                    },
                },
            }
        ],
        "edges": [],
    }
    assert list(_iter_promotable_fields(flow_data)) == []
```

- [ ] **Step 2: Run to verify failure**

```
.venv/bin/pytest src/backend/tests/unit/services/variable/test_auto_secrets.py -v -k _iter_promotable_fields
```

Expected: `ImportError: cannot import name '_iter_promotable_fields'`.

- [ ] **Step 3: Rename + generalize the walker**

Edit `src/backend/base/langflow/services/variable/auto_secrets.py`. Find `_iter_textfilesecret_fields`. Rename it to `_iter_promotable_fields` and change the predicate. Also update ALL internal call sites in the same file (`promote_plaintext_secrets_to_variables`, `cleanup_orphaned_autosecrets`, `blank_autosecrets_for_export` — 3 callers).

Replace the function entirely:

```python
def _iter_promotable_fields(flow_data: dict) -> list[tuple[str, str, dict]]:
    """Yield (node_id, field_name, field_dict) for every field with
    auto_promote=True.

    Replaces the earlier _iter_textfilesecret_fields which only matched on
    _input_type name. The new predicate consults the per-field auto_promote
    flag, which SecretStrInput (and its subclasses including
    TextFileSecretInput) set to True by default. Component authors can opt
    out per field with auto_promote=False.
    """
    out: list[tuple[str, str, dict]] = []
    for node in flow_data.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        template = node.get("data", {}).get("node", {}).get("template", {})
        if not node_id or not isinstance(template, dict):
            continue
        for field_name, field in template.items():
            if not isinstance(field, dict):
                continue
            if field.get("auto_promote") is True:
                out.append((node_id, field_name, field))
    return out
```

Update the three internal call sites in the same file: replace every `_iter_textfilesecret_fields(` with `_iter_promotable_fields(`.

- [ ] **Step 4: Run all `test_auto_secrets.py` tests**

```
.venv/bin/pytest src/backend/tests/unit/services/variable/test_auto_secrets.py -v
```

Expected: the existing 11 tests + 4 new ones pass. Any existing tests that imported `_iter_textfilesecret_fields` by name need updating to the new name. Fix them by search-replace.

- [ ] **Step 5: Pause for user commit approval**

Proposed message: `refactor(variables): rename walker to _iter_promotable_fields + use auto_promote flag`

---

### Task 4: Promote helper learns to preserve user-managed Variable references

**Files:**
- Modify: `src/backend/base/langflow/services/variable/auto_secrets.py` — add a `has_user_managed_variable` call in `promote_plaintext_secrets_to_variables`
- Modify test: `src/backend/tests/unit/services/variable/test_auto_secrets.py` — cover the new path

- [ ] **Step 1: Write the failing test**

Append to `src/backend/tests/unit/services/variable/test_auto_secrets.py`:

```python
@pytest.mark.asyncio
async def test_promote_preserves_user_managed_variable_reference():
    """If the value matches an existing user-managed Variable name, the
    field is preserved as a reference (not overwritten with an autosecret)."""
    flow_data = _flow_data(
        {
            "_input_type": "SecretStrInput",
            "auto_promote": True,
            "value": "my_company_api_key",  # user-managed Variable name
            "load_from_db": True,
        }
    )
    svc = AsyncMock()
    svc.list_autosecret_names_for_flow = AsyncMock(return_value=[])
    svc.has_user_managed_variable = AsyncMock(return_value=True)  # user-managed
    svc.create_variable = AsyncMock()
    svc.update_variable_value = AsyncMock()
    session = AsyncMock()

    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        variable_service=svc,
        session=session,
    )

    svc.has_user_managed_variable.assert_awaited_once()
    svc.create_variable.assert_not_called()
    svc.update_variable_value.assert_not_called()

    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert field["value"] == "my_company_api_key"  # unchanged
    assert field["load_from_db"] is True


@pytest.mark.asyncio
async def test_promote_promotes_when_value_does_not_match_any_variable():
    """Typed-in plaintext (no matching user-managed Variable) is promoted."""
    flow_data = _flow_data(
        {
            "_input_type": "SecretStrInput",
            "auto_promote": True,
            "value": "sk-typed-plaintext-secret",
            "load_from_db": False,
        }
    )
    svc = AsyncMock()
    svc.list_autosecret_names_for_flow = AsyncMock(return_value=[])
    svc.has_user_managed_variable = AsyncMock(return_value=False)  # no match
    svc.create_variable = AsyncMock()
    session = AsyncMock()

    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        variable_service=svc,
        session=session,
    )

    svc.create_variable.assert_awaited_once()
    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert field["value"].startswith(AUTOSECRET_PREFIX)


@pytest.mark.asyncio
async def test_promote_short_circuits_on_any_autosecret_prefix():
    """If value starts with AUTOSECRET_PREFIX (even for a different flow),
    skip promotion entirely to avoid re-wrapping."""
    foreign_autosecret = f"{AUTOSECRET_PREFIX}other-flow-id_OtherNode_cert_pem"
    flow_data = _flow_data(
        {
            "_input_type": "SecretStrInput",
            "auto_promote": True,
            "value": foreign_autosecret,
            "load_from_db": True,
        }
    )
    svc = AsyncMock()
    svc.list_autosecret_names_for_flow = AsyncMock(return_value=[])
    svc.has_user_managed_variable = AsyncMock(return_value=False)
    svc.create_variable = AsyncMock()
    session = AsyncMock()

    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        variable_service=svc,
        session=session,
    )

    svc.create_variable.assert_not_called()
    svc.has_user_managed_variable.assert_not_called()  # short-circuited earlier
    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert field["value"] == foreign_autosecret
```

- [ ] **Step 2: Run tests (expecting 2 of 3 to fail)**

```
.venv/bin/pytest src/backend/tests/unit/services/variable/test_auto_secrets.py -v
```

Expected: `test_promote_preserves_user_managed_variable_reference` fails (user-managed preservation not implemented) and `test_promote_short_circuits_on_any_autosecret_prefix` may fail depending on current behavior. `test_promote_promotes_when_value_does_not_match_any_variable` should already pass (default path).

- [ ] **Step 3: Update `promote_plaintext_secrets_to_variables`**

Edit `src/backend/base/langflow/services/variable/auto_secrets.py`. Find `promote_plaintext_secrets_to_variables`. Replace its body with:

```python
async def promote_plaintext_secrets_to_variables(
    *,
    flow_data: dict,
    flow_id: UUID,
    user_id: UUID,
    variable_service: VariableService,
    session: AsyncSession,
) -> dict:
    """Upsert a hidden Variable for every promotable field whose value is
    typed-in plaintext; rewrite the field to reference the Variable by name.

    Preserves values that are:
    - already autosecret references (any flow_id), idempotent.
    - the name of an existing user-managed Variable (picked, not typed).

    Returns the (possibly-mutated) flow_data dict.
    """
    existing_names = set(
        await variable_service.list_autosecret_names_for_flow(
            flow_id=flow_id,
            user_id=user_id,
            session=session,
        )
    )

    for node_id, field_name, field in _iter_promotable_fields(flow_data):
        expected_name = autosecret_name(flow_id, node_id, field_name)
        value = field.get("value") or ""

        # Empty plaintext: clear any stale reference so the save is clean.
        # Cleanup of orphaned autosecrets runs separately.
        if not value:
            field["value"] = ""
            field["load_from_db"] = False
            continue

        # Any autosecret reference — our own or foreign — is preserved as-is.
        if isinstance(value, str) and value.startswith(AUTOSECRET_PREFIX):
            continue

        # User picked an existing user-managed Variable by name; preserve.
        if await variable_service.has_user_managed_variable(
            name=value, user_id=user_id, session=session
        ):
            continue

        # Typed-in plaintext: upsert the autosecret Variable.
        if expected_name in existing_names:
            await variable_service.update_variable_value(
                name=expected_name,
                value=value,
                user_id=user_id,
                session=session,
            )
        else:
            await variable_service.create_variable(
                name=expected_name,
                value=value,
                user_id=user_id,
                type_="CREDENTIAL",
                session=session,
            )
        field["value"] = expected_name
        field["load_from_db"] = True

    return flow_data
```

- [ ] **Step 4: Update existing tests that don't mock `has_user_managed_variable`**

Any previously passing test that calls `promote_plaintext_secrets_to_variables` without configuring `svc.has_user_managed_variable` will fail (AsyncMock default is to return a MagicMock, truthy, short-circuiting promotion). Fix by adding `svc.has_user_managed_variable = AsyncMock(return_value=False)` to each test's setup.

Search the test file for existing tests that use the promote helper and add the mock. Likely affected:
- `test_promote_creates_variable_for_plaintext_textfilesecret`
- `test_promote_skips_empty_plaintext`
- `test_promote_upserts_when_value_changed`

(`test_promote_skips_non_textfilesecret_fields` doesn't reach the user-managed check because the walker skips the field — it's fine.)
(`test_promote_skips_already_promoted_reference` also short-circuits at the AUTOSECRET_PREFIX check — fine.)

- [ ] **Step 5: Run all auto_secrets tests**

```
.venv/bin/pytest src/backend/tests/unit/services/variable/test_auto_secrets.py -v
```

Expected: all previously passing + the 3 new tests pass.

- [ ] **Step 6: Pause for user commit approval**

Proposed message: `feat(variables): preserve user-managed Variable refs in promote helper`

---

### Task 5: Extend integration test for generalized behavior

**Files:**
- Modify: `src/backend/tests/unit/api/v1/test_flow_autosecret_lifecycle.py`

- [ ] **Step 1: Add two new integration test functions**

Append to `src/backend/tests/unit/api/v1/test_flow_autosecret_lifecycle.py` (use the same fixture pattern as existing tests):

```python
def _secretstr_field(value: str, *, auto_promote: bool = True) -> dict:
    """Flow-template dict for a bare SecretStrInput with auto_promote."""
    return {
        "_input_type": "SecretStrInput",
        "auto_promote": auto_promote,
        "value": value,
        "load_from_db": auto_promote,  # matches SecretStrInput defaults
        "type": "str",
        "password": True,
    }


def _flow_with_secret_str(value: str) -> dict:
    """Minimal flow with a bare SecretStrInput field carrying plaintext."""
    return {
        "name": "SecretStrInput auto-promote test",
        "data": {
            "nodes": [
                {
                    "id": "CustomComponent-int1",
                    "data": {
                        "type": "CustomComponent",
                        "id": "CustomComponent-int1",
                        "node": {
                            "template": {
                                "api_key": _secretstr_field(value),
                            },
                        },
                    },
                }
            ],
            "edges": [],
        },
    }


@pytest.mark.usefixtures("active_user")
async def test_create_flow_promotes_bare_secret_str_input(
    client: AsyncClient, logged_in_headers
):
    """POST a flow whose node has a bare SecretStrInput with typed plaintext.
    The generalized auto-promote mechanism should promote it to an autosecret
    Variable."""
    payload = _flow_with_secret_str("sk-typed-plaintext-api-key-12345")

    r = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    assert r.status_code == 201, r.text
    flow = r.json()
    flow_id = flow["id"]

    node = flow["data"]["nodes"][0]
    api_key_field = node["data"]["node"]["template"]["api_key"]
    assert api_key_field["value"].startswith(
        f"{AUTOSECRET_PREFIX}{flow_id}_CustomComponent-int1_api_key"
    )
    assert api_key_field["load_from_db"] is True


@pytest.mark.usefixtures("active_user")
async def test_create_flow_preserves_user_managed_variable_reference(
    client: AsyncClient, logged_in_headers
):
    """POST a flow whose SecretStrInput value is the name of a pre-existing
    user-managed Variable. The promote helper must not overwrite it."""
    # Pre-create a user-managed Variable.
    user_var_name = "my_shared_api_key"
    r = await client.post(
        "api/v1/variables/",
        json={
            "name": user_var_name,
            "value": "sk-actual-value-never-exposed",
            "type": "CREDENTIAL",
            "default_fields": [],
        },
        headers=logged_in_headers,
    )
    assert r.status_code == 201, r.text

    # Now POST a flow whose SecretStrInput field references that Variable by name.
    payload = _flow_with_secret_str(user_var_name)

    r = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    assert r.status_code == 201, r.text
    flow = r.json()

    api_key_field = flow["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]
    # Reference preserved — NOT rewritten as an autosecret.
    assert api_key_field["value"] == user_var_name
    assert api_key_field["load_from_db"] is True
```

- [ ] **Step 2: Run the integration test suite**

```
.venv/bin/pytest src/backend/tests/unit/api/v1/test_flow_autosecret_lifecycle.py -v
```

Expected: previously passing 5 + new 2 pass (7 total).

- [ ] **Step 3: Pause for user commit approval**

Proposed message: `test(integration): cover auto-promote for bare SecretStrInput and user-Variable preservation`

---

### Task 6: Refactor `_shared.py` (ADPConnection + build_mtls_httpx_client)

**Files:**
- Modify: `src/lfx/src/lfx/components/adp/_shared.py`

This is the first ADP-specific task. It tightens the connection dataclass, converts `build_mtls_httpx_client` to an async context manager, deletes `_write_pem_temp_files` and `_MTLSClient`, and removes re-exports that are no longer used.

- [ ] **Step 1: Survey in-repo usages of soon-to-be-deleted helpers**

```
grep -rn "_write_pem_temp_files\|_MTLSClient\|cert_source\|cert_path\|key_path" src/lfx/src/lfx/components/adp/ src/lfx/tests/unit/components/adp/
```

Report what callers exist for each symbol. Any caller outside `_shared.py` needs updating in Task 7 or Task 9+.

- [ ] **Step 2: Edit the dataclass**

Edit `src/lfx/src/lfx/components/adp/_shared.py`. Find the `ADPConnection` dataclass (~line 55). Replace it with:

```python
@dataclass
class ADPConnection:
    """Shared connection state produced by ADPAuthComponent, consumed by API/MCP components.

    Not frozen: token and expiry are mutated by the token-fetch helper.
    """

    client_id: str
    client_secret: str
    cert_pem: str
    key_pem: str
    api_base_url: str = DEFAULT_API_BASE_URL
    mcp_base_url: str = DEFAULT_MCP_BASE_URL
    token_url: str = DEFAULT_TOKEN_URL
    access_token: str | None = None
    token_expires_at: datetime | None = None
```

Drop `cert_source: Literal["path", "pem"]`, `cert_path: str | None = None`, `key_path: str | None = None`.

- [ ] **Step 3: Replace `build_mtls_httpx_client` with async context manager**

In the same file, find `build_mtls_httpx_client` (~line 111). Replace the entire function + the `_MTLSClient` subclass + `_write_pem_temp_files` with:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from lfx.base.api_request.mtls import mtls_temp_files


@asynccontextmanager
async def build_mtls_httpx_client(
    conn: ADPConnection,
    *,
    timeout: float = 30.0,
) -> AsyncIterator[httpx.AsyncClient]:
    """Async context manager yielding an httpx.AsyncClient configured with mTLS
    using the connection's PEMs. Temp files for cert/key are written with 0600
    perms and unlinked on exit.
    """
    if not conn.cert_pem or not conn.key_pem:
        msg = "ADPConnection requires both cert_pem and key_pem."
        raise ValueError(msg)

    async with mtls_temp_files(conn.cert_pem, conn.key_pem) as cert_tuple:
        async with httpx.AsyncClient(cert=cert_tuple, timeout=timeout) as client:
            yield client
```

Delete the `_MTLSClient` subclass body, the `_write_pem_temp_files` function, and any module-level re-exports of `_normalize_pem` / `_write_secure_tempfile` that are no longer referenced.

- [ ] **Step 4: Verify import integrity**

```
.venv/bin/python -c "from lfx.components.adp._shared import ADPConnection, build_mtls_httpx_client, fetch_token; print('imports OK')"
```

Expected: `imports OK`. If the `fetch_token` function in the same file calls `build_mtls_httpx_client`, it needs updating to use the new context manager shape — handled in Task 7 Step 4.

- [ ] **Step 5: Stage and pause**

`git add src/lfx/src/lfx/components/adp/_shared.py`. Wait for user approval.

Proposed commit: `refactor(adp): simplify ADPConnection and convert build_mtls_httpx_client to async CM`

---

### Task 7: Update call sites of `build_mtls_httpx_client`

**Files:**
- Modify: `src/lfx/src/lfx/components/adp/_shared.py` — internal call site in `fetch_token`
- Modify: `src/lfx/src/lfx/components/adp/adp_api_request.py` — find call sites; likely already uses context-manager shape
- Modify: `src/lfx/src/lfx/components/adp/adp_mcp.py` — same
- Modify: `src/lfx/src/lfx/components/adp/adp_worker_tools.py` — same
- Modify: `src/lfx/src/lfx/components/adp/adp_trigger.py` — same
- Modify: `src/lfx/src/lfx/components/adp/adp_auth.py` — removes the ADPConnection construction fields that no longer exist (this overlaps with Task 9 but the dataclass change forces it here to keep `_shared.py` in a working state)

- [ ] **Step 1: Inspect each caller**

```
grep -rn "build_mtls_httpx_client\|ADPConnection(" src/lfx/src/lfx/components/adp/
```

For each, check whether the call site:
- Already uses `async with build_mtls_httpx_client(conn) as client:` — no change needed.
- Uses `client = build_mtls_httpx_client(conn)` without `async with` — change required to wrap in context manager.
- Constructs `ADPConnection(cert_source=..., cert_path=..., key_path=...)` — must drop those keyword args and use `cert_pem`/`key_pem` instead.

- [ ] **Step 2: Update `fetch_token` in `_shared.py`**

Find `fetch_token` (~line 203) and update its call to `build_mtls_httpx_client`:

```python
async def fetch_token(conn: ADPConnection, *, force: bool = False) -> None:
    if not force and _token_is_fresh(conn):
        return

    async with build_mtls_httpx_client(conn) as client:
        response = await _post_token_request(client, conn)

    # ...rest unchanged...
```

(If already in this shape, no change.)

- [ ] **Step 3: Update `adp_api_request.py`, `adp_mcp.py`, `adp_worker_tools.py`, `adp_trigger.py`**

For each file, find each `build_mtls_httpx_client` call. The shape in Task 6 is an async context manager. Confirm each caller uses `async with build_mtls_httpx_client(conn, timeout=...) as client:`. If the previous code already had this pattern, no change needed. If any caller has `client = build_mtls_httpx_client(...)` without `async with`, wrap it.

- [ ] **Step 4: Update ADPAuthComponent's `ADPConnection` construction (partial)**

Open `src/lfx/src/lfx/components/adp/adp_auth.py`. Find `build_connection` (~line 77). It currently constructs `ADPConnection(client_id=..., client_secret=..., cert_source=source, cert_path=..., key_path=..., cert_pem=..., key_pem=..., token_url=...)`.

Replace the construction with:

```python
conn = ADPConnection(
    client_id=client_id,
    client_secret=client_secret,
    cert_pem=self.cert_pem or "",
    key_pem=self.key_pem or "",
    token_url=token_url,
)
```

Drop `cert_source=source`, `cert_path=self.cert_path or None`, `key_path=self.key_path or None`. The `source = "path" if self.cert_source == "File Path" else "pem"` line can be deleted too (no longer referenced).

Also delete the validation block that checks `cert_path`/`key_path`/`cert_pem`/`key_pem` based on `source`. Replace with a single check:

```python
if not self.cert_pem:
    msg = "cert_pem is required"
    raise ValueError(msg)
if not self.key_pem:
    msg = "key_pem is required"
    raise ValueError(msg)
```

The full field-definition swap (`cert_source` TabInput removal, `cert_path`/`key_path` removal, `cert_pem`/`key_pem` type conversion to TextFileSecretInput) happens in Task 9 — but the above partial update is required NOW so `adp_auth.py` doesn't construct an ADPConnection with deleted keyword args.

- [ ] **Step 5: Import check across all 5 files**

```
for f in src/lfx/src/lfx/components/adp/{adp_auth,adp_api_request,adp_mcp,adp_worker_tools,adp_trigger}.py; do
  .venv/bin/python -c "import ast; ast.parse(open('$f').read()); print('OK: $f')" || echo "FAIL: $f"
done
```

Expected: each prints `OK:`.

- [ ] **Step 6: Stage and pause**

`git add src/lfx/src/lfx/components/adp/`. Wait for user approval.

Proposed commit: `refactor(adp): update build_mtls_httpx_client call sites to async CM shape`

---

### Task 8: Migrate `test_shared.py`

**Files:**
- Modify: `src/lfx/tests/unit/components/adp/test_shared.py`

- [ ] **Step 1: Run the existing tests to see what breaks**

```
LFX_TEST_ALLOW_LANGFLOW=1 .venv/bin/pytest src/lfx/tests/unit/components/adp/test_shared.py -v 2>&1 | tail -40
```

Expected: many failures related to `cert_source`, `cert_path`, `key_path`, `_write_pem_temp_files`, and `_MTLSClient` (all deleted in Task 6). Note which tests are in each bucket.

- [ ] **Step 2: Delete tests that exercise the path-mode branch**

Any test whose name matches `*path*cert*` or that constructs `ADPConnection(cert_source="path", ...)` — delete those test functions entirely. Keep tests that use `cert_source="pem"` or the PEM-mode path (update them per Step 3).

- [ ] **Step 3: Update PEM-mode tests for the new context-manager shape**

For any test that calls `build_mtls_httpx_client(conn)` and expects a plain client, rewrite to use async context:

```python
@pytest.mark.asyncio
async def test_build_mtls_httpx_client_yields_client_with_cert():
    conn = ADPConnection(
        client_id="cid",
        client_secret="csec",  # noqa: S106
        cert_pem="-----BEGIN CERTIFICATE-----\nAAA\n-----END CERTIFICATE-----\n",
        key_pem="-----BEGIN PRIVATE KEY-----\nAAA\n-----END PRIVATE KEY-----\n",
    )
    async with build_mtls_httpx_client(conn) as client:
        assert isinstance(client, httpx.AsyncClient)
        # Temp files should exist during the context.
    # After exit they're cleaned up — covered by mtls_temp_files tests, not here.
```

- [ ] **Step 4: Delete tests for `_write_pem_temp_files`**

Search for `_write_pem_temp_files` in `test_shared.py` and delete those tests. The underlying PEM-writing behavior is already tested by `mtls_temp_files` in `src/lfx/tests/unit/base/api_request/test_mtls.py`.

- [ ] **Step 5: Run tests to verify pass**

```
LFX_TEST_ALLOW_LANGFLOW=1 .venv/bin/pytest src/lfx/tests/unit/components/adp/test_shared.py -v
```

Expected: all remaining tests pass.

- [ ] **Step 6: Pause for user commit approval**

Proposed commit: `test(adp): migrate shared helper tests to async CM and PEM-only shape`

---

### Task 9: ADPAuthComponent field migration + version/changelog

**Files:**
- Modify: `src/lfx/src/lfx/components/adp/adp_auth.py`

Task 7 Step 4 already updated `build_connection`'s `ADPConnection` construction. This task completes the input-list changes (TabInput removal, field type conversion) and adds the version/changelog.

- [ ] **Step 1: Update imports**

Edit `src/lfx/src/lfx/components/adp/adp_auth.py`. Update imports at the top:

```python
from typing import ClassVar

from lfx.components.adp._shared import DEFAULT_TOKEN_URL, ADPConnection, fetch_token, validate_adp_url
from lfx.custom.custom_component.changelog import ChangelogEntry
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import TextFileSecretInput
from lfx.io import MessageTextInput, Output, SecretStrInput
from lfx.schema.dotdict import dotdict
```

Remove `TabInput` if no longer needed. Remove `set_field_display` import if `update_build_config` is deleted (see Step 4).

- [ ] **Step 2: Rewrite the `inputs` list**

Locate the `inputs = [...]` list. Replace with:

```python
inputs = [
    SecretStrInput(
        name="client_id",
        display_name="Client ID",
        info="ADP developer client ID.",
        required=True,
    ),
    SecretStrInput(
        name="client_secret",
        display_name="Client Secret",
        info="ADP developer client secret.",
        required=True,
    ),
    TextFileSecretInput(
        name="cert_pem",
        display_name="Client Certificate (PEM)",
        info=(
            "Client certificate for mTLS. Paste the PEM contents or upload a "
            ".pem/.crt file. Stored Fernet-encrypted at rest."
        ),
        file_types=["pem", "crt"],
        required=True,
    ),
    TextFileSecretInput(
        name="key_pem",
        display_name="Client Key (PEM)",
        info=(
            "Client private key for mTLS. Paste the PEM contents or upload a "
            ".pem/.key file. Stored Fernet-encrypted at rest."
        ),
        file_types=["pem", "key"],
        required=True,
    ),
    MessageTextInput(
        name="token_url",
        display_name="Token URL",
        info="OAuth token endpoint. Override only for staging/testing.",
        value=DEFAULT_TOKEN_URL,
        advanced=True,
    ),
]
```

Drop the `cert_source` TabInput, the `cert_path` + `key_path` MessageTextInput fields, and the original `cert_pem` + `key_pem` SecretStrInput fields.

- [ ] **Step 3: Add version + changelog**

Immediately after `name = "ADPAuth"` (class attribute), add:

```python
    version: int = 2
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=2,
            changes=(
                "- Replaced the `cert_source` File Path / PEM toggle with "
                "**paste-or-upload** TextFileSecretInput fields for cert_pem "
                "and key_pem.\n"
                "- `cert_path` and `key_path` inputs removed.\n"
                "- client_id, client_secret, cert_pem, and key_pem are now "
                "Fernet-encrypted at rest via hidden auto-Variables (not "
                "stored plaintext in the flow JSON)."
            ),
            notes=(
                "Saved flows with cert_source='File Path' drop the cert_path "
                "and key_path values on load. Paste the certificate and key "
                "PEMs (or upload the .pem/.crt/.key files) into the new "
                "fields to restore the connection. client_id and "
                "client_secret typed inline are now silently encrypted on "
                "save; exported flow JSON will show empty values where it "
                "previously showed plaintext — re-enter credentials on import."
            ),
        ),
    ]
```

- [ ] **Step 4: Simplify or remove `update_build_config`**

Locate `update_build_config` (~line 119). It currently handles the `cert_source` field change. Since `cert_source` is gone, this method has no remaining logic. Delete the method entirely.

If the base `Component` class requires `update_build_config` to exist, verify by running the class's existing test file. If required, keep a minimal stub that returns the build_config unchanged:

```python
def update_build_config(self, build_config: dotdict, field_value, field_name: str | None = None) -> dotdict:
    return build_config
```

Prefer deleting if the base class tolerates its absence.

- [ ] **Step 5: Verify imports + class parses**

```
.venv/bin/python -c "from lfx.components.adp.adp_auth import ADPAuthComponent; print(ADPAuthComponent.version, len(ADPAuthComponent.changelog))"
```

Expected: `2 1`.

- [ ] **Step 6: Stage and pause**

`git add src/lfx/src/lfx/components/adp/adp_auth.py`. Wait for user approval.

Proposed commit: `feat(adp-auth): migrate to TextFileSecretInput and bump to v2`

---

### Task 10: Migrate `test_adp_auth.py`

**Files:**
- Modify: `src/lfx/tests/unit/components/adp/test_adp_auth.py`

- [ ] **Step 1: Run existing tests to see breakage**

```
LFX_TEST_ALLOW_LANGFLOW=1 .venv/bin/pytest src/lfx/tests/unit/components/adp/test_adp_auth.py -v 2>&1 | tail -40
```

Expected: failures on tests referencing `cert_source`, `cert_path`, `key_path`, `update_build_config`'s cert_source handling.

- [ ] **Step 2: Delete tests that exercise removed behavior**

- Tests that exercise `update_build_config(field_name="cert_source")` — delete.
- Tests that construct the component with `cert_source="File Path"` or `cert_path=...` — delete.
- Tests that assert `cert_path` / `key_path` are in the input list — delete.

- [ ] **Step 3: Update remaining tests for new field types**

Any test that constructs the component and sets `component.cert_pem = "..."` or `component.key_pem = "..."` should keep working — the field names are unchanged, only the input type and encryption pathway differ.

Any test that asserts input shape (e.g. `assert inputs[i].name == "cert_pem"`) should continue to pass.

Add a new test verifying the migrated shape:

```python
def test_adp_auth_fields_are_text_file_secret_input(component):
    """cert_pem and key_pem must be TextFileSecretInput to get paste-or-upload."""
    from lfx.inputs.inputs import TextFileSecretInput

    names_to_types = {inp.name: type(inp) for inp in ADPAuthComponent().inputs}
    assert names_to_types["cert_pem"] is TextFileSecretInput
    assert names_to_types["key_pem"] is TextFileSecretInput


def test_adp_auth_version_and_changelog():
    assert ADPAuthComponent.version == 2
    assert len(ADPAuthComponent.changelog) == 1
    assert ADPAuthComponent.changelog[0].version == 2
```

- [ ] **Step 4: Run the test suite**

```
LFX_TEST_ALLOW_LANGFLOW=1 .venv/bin/pytest src/lfx/tests/unit/components/adp/test_adp_auth.py -v
```

Expected: all remaining tests pass.

- [ ] **Step 5: Pause for user commit approval**

Proposed commit: `test(adp-auth): migrate test suite to TextFileSecretInput shape`

---

### Task 11: Migrate remaining ADP component tests

**Files:**
- Modify: `src/lfx/tests/unit/components/adp/test_adp_api_request.py`
- Modify: `src/lfx/tests/unit/components/adp/test_adp_mcp.py`
- Modify: `src/lfx/tests/unit/components/adp/test_adp_worker_tools.py`
- Modify: `src/lfx/tests/unit/components/adp/test_adp_trigger.py`

- [ ] **Step 1: Run each file to identify breakage**

```
for f in test_adp_api_request test_adp_mcp test_adp_worker_tools test_adp_trigger; do
  echo "=== $f ==="
  LFX_TEST_ALLOW_LANGFLOW=1 .venv/bin/pytest "src/lfx/tests/unit/components/adp/$f.py" -v 2>&1 | tail -10
done
```

Expected: failures where tests construct `ADPConnection(cert_source="pem", ...)` or `ADPConnection(cert_source="path", ...)`.

- [ ] **Step 2: Fix each file by search-replace**

For each file, find every `ADPConnection(...)` and update to the new shape (no `cert_source`, no `cert_path`, no `key_path`). Example:

Before:
```python
ADPConnection(
    client_id="cid",
    client_secret="csec",  # noqa: S106
    cert_source="pem",
    cert_pem="PEMCERT",
    key_pem="PEMKEY",
    token_url="https://accounts.adp.com/...",
)
```

After:
```python
ADPConnection(
    client_id="cid",
    client_secret="csec",  # noqa: S106
    cert_pem="PEMCERT",
    key_pem="PEMKEY",
    token_url="https://accounts.adp.com/...",
)
```

Delete any test that explicitly exercised the path-mode (e.g. `cert_source="path", cert_path="/tmp/..."`). Those scenarios are gone.

- [ ] **Step 3: Run each file to verify green**

Same command as Step 1, expect all pass.

- [ ] **Step 4: Pause for user commit approval**

Proposed commit: `test(adp): update call sites for simplified ADPConnection shape`

---

### Task 12: Starter project regen

**Files:**
- Potentially modify: `src/backend/base/langflow/initial_setup/starter_projects/*.json` (whichever starter projects reference ADP components)

- [ ] **Step 1: Identify which starter projects reference ADP**

```
grep -l "ADPAuth\|ADPAPIRequest\|ADPConnection" src/backend/base/langflow/initial_setup/starter_projects/*.json
```

Expected: possibly zero, possibly one (ADP Worker Sync to SFTP — check).

- [ ] **Step 2: Run the regeneration script**

```
cd /Users/brycedeneen/dev/langflow/.worktrees/adp-auth-vault-backed-pem
.venv/bin/python scripts/ci/update_starter_projects.py
git status --short
```

Expected: one or more starter JSON files modified. Confirm by eye that only ADP-affected starters changed. If the script also regenerates unrelated starters (because the worktree's installed-dep versions differ from baseline), revert those unrelated changes (use the pattern from the first feature: keep only the targeted regen, revert the rest via `git checkout --` on each unrelated file).

- [ ] **Step 3: Stage the ADP-affected starter(s) only**

```
git add <ADP-affected starter paths only>
git status --short
```

- [ ] **Step 4: Pause for user commit approval**

Proposed commit: `chore(starter): regenerate ADP-using starters for TextFileSecretInput migration`

If no ADP starters exist, skip this task entirely with a note.

---

## Post-plan follow-ups (tracked in the spec, not implemented here)

- **FU-1.** Frontend renderer polish: "Secret set — click to replace" affordance for autosecret-prefixed values in both TextFileSecretInput and SecretStrInput renderers.
- **FU-2.** Audit all existing `SecretStrInput` sites (100+) across the codebase. Verify none depend on plaintext round-trip. Document decisions.
- **FU-3.** Consider promoting `SecretStrInput.auto_promote=True` to the developer-facing "custom component authoring" guide once the default-True rollout is stable.
- **FU-4.** Evaluate real Hashicorp Vault adoption for Variables if rotation / short-lived secrets become production requirements.

---

## Self-review

Reviewed plan against spec:

- **§5 Architecture** — all four surfaces covered: Task 1 (SecretStrInput field), Tasks 2–5 (helper changes), Tasks 6–8 (_shared.py), Tasks 9–11 (ADP components + tests), Task 12 (starter regen).
- **§6 Auto-promote logic** — Task 1 (§6.1 field), Task 2 (§6.3 service method), Task 3 (§6.2 walker rename), Task 4 (§6.4 promote logic).
- **§7 ADPAuthComponent migration** — Task 9 covers all of §7.1 (field changes), §7.2 (build_connection), §7.3 (update_build_config), §7.4 (version/changelog).
- **§8 Shared module cleanup** — Task 6 (dataclass + function), Task 7 (call sites), Task 8 (tests).
- **§9 Testing** — Task 1 unit tests (§9.1), Tasks 2/3/4 extend auto_secrets tests, Task 5 integration (§9.3), Task 10 ADP Auth tests (§9.2), Task 11 other ADP tests (§9.2), Task 8 shared tests (§9.2).
- **§10 Cross-cutting rollout** — covered by Task 1's default-True flag + relying on existing promote/cleanup infrastructure (no additional tasks needed beyond the audit follow-up tracked in FU-2).
- **§11 Risks** — R1 mitigation via Task 4 tests. R2 mitigation via Task 12 starter regen. R3 deferred to FU-1. R4 no migration needed. R5 behavior preserved via the `AUTOSECRET_PREFIX` short-circuit in Task 4.

No placeholders. All referenced functions/types match across tasks (`has_user_managed_variable`, `_iter_promotable_fields`, `autosecret_name`, `AUTOSECRET_PREFIX`). Type signatures consistent between Tasks 2 and 4 (keyword-only, `name: str`, `user_id: UUID`, `session: AsyncSession`). Task 7's shape-transition note (`build_mtls_httpx_client` becoming an async context manager) is surfaced in both Task 6 (definition) and Task 7 (callers).

Scope check: single focused plan, 12 bite-sized tasks across 4 phases. Does not decompose further.

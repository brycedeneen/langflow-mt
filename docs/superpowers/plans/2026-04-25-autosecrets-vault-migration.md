# Auto-Secrets → Vault Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate auto-promoted `SecretStrInput` field values from the Postgres `variable` table to HashiCorp Vault via the existing `lfx.services.secret_store.SecretStore` interface, and bundle the Issue 1 round-trip fix so empty-on-resave preserves the existing secret.

**Architecture:** Replace Postgres reads/writes inside `auto_secrets.py` with `SecretStore` calls keyed by `{org_id}/flows/{flow_id}/autosecrets/{node_id}/{field_name}`. Introduce a `resolver.py` that dispatches `load_from_db` lookups by marker prefix (`__autosecret|...` → Vault, anything else → existing user-managed Variable path). Switch the marker delimiter from `_` to `|` for clean parsing. Treat empty-value-on-save with an existing Vault secret as "untouched, preserve" instead of "cleared, wipe."

**Tech Stack:** Python 3.12, Pydantic, `hvac` (already pulled in by `VaultSecretStore`), pytest, pytest-asyncio. `InMemorySecretStore` (already shipped) is used for unit tests.

**Spec:** `docs/superpowers/specs/2026-04-25-autosecrets-vault-migration-design.md`

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `src/backend/base/langflow/services/variable/auto_secrets.py` | Modify | New constants/helpers; rewritten `promote_*`, `cleanup_*`, `delete_*` to use SecretStore; `blank_*` body unchanged. |
| `src/backend/base/langflow/services/variable/resolver.py` | Create | `resolve_secret_reference` — dispatch by marker prefix. |
| `src/backend/base/langflow/services/variable/service.py` | Modify | Remove `list_autosecret_names_for_flow` (dead after migration). |
| `src/backend/base/langflow/interface/initialize/loading.py` | Modify | `update_params_with_load_from_db_fields` calls resolver instead of `custom_component.get_variable`. |
| `src/backend/base/langflow/api/v1/flows.py` | Modify | Three call sites pass `secret_store` (DI) into the autosecret functions in addition to `variable_service`. |
| `src/backend/tests/unit/services/variable/test_auto_secrets.py` | Modify | Replace Variable mocks with `InMemorySecretStore`; cover all five branches incl. Issue 1 fix. |
| `src/backend/tests/unit/services/variable/test_resolver.py` | Create | Resolver dispatch + autosecret lookup unit tests. |
| `src/backend/tests/unit/services/variable/test_marker.py` | Create | Round-trip + parse-error tests for the new helpers. |
| `src/backend/tests/integration/services/test_autosecrets_vault.py` | Create | Real-Vault round-trip (gated like `test_vault_secret_store.py`). |

---

## Task 1: New constants + helpers in `auto_secrets.py`

**Files:**
- Modify: `src/backend/base/langflow/services/variable/auto_secrets.py`
- Create: `src/backend/tests/unit/services/variable/test_marker.py`

- [ ] **Step 1: Write failing tests for the new helpers**

Create `src/backend/tests/unit/services/variable/test_marker.py`:

```python
"""Tests for autosecret marker / Vault path helpers."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from langflow.services.variable.auto_secrets import (
    AUTOSECRET_PREFIX,
    LEGACY_AUTOSECRET_PREFIX,
    autosecret_marker,
    autosecret_vault_path,
    parse_autosecret_marker,
)


FLOW_ID = UUID("4312a8ac-22db-4d86-805e-86d19451c489")
ORG_ID = UUID("11111111-2222-3333-4444-555555555555")


def test_prefixes_are_distinct():
    assert AUTOSECRET_PREFIX == "__autosecret|"
    assert LEGACY_AUTOSECRET_PREFIX == "__autosecret_"
    assert AUTOSECRET_PREFIX != LEGACY_AUTOSECRET_PREFIX


def test_autosecret_marker_format():
    marker = autosecret_marker(FLOW_ID, "ADPAuth-fMRCo", "client_secret")
    assert marker == f"__autosecret|{FLOW_ID}|ADPAuth-fMRCo|client_secret"
    assert marker.startswith(AUTOSECRET_PREFIX)


def test_autosecret_vault_path_format():
    path = autosecret_vault_path(ORG_ID, FLOW_ID, "ADPAuth-fMRCo", "cert_pem")
    assert path == f"{ORG_ID}/flows/{FLOW_ID}/autosecrets/ADPAuth-fMRCo/cert_pem"


def test_parse_round_trip():
    marker = autosecret_marker(FLOW_ID, "ADPAuth-fMRCo", "client_secret")
    flow_id, node_id, field_name = parse_autosecret_marker(marker)
    assert flow_id == FLOW_ID
    assert node_id == "ADPAuth-fMRCo"
    assert field_name == "client_secret"


def test_parse_handles_underscores_in_node_id_and_field_name():
    marker = autosecret_marker(FLOW_ID, "Some_Node-1", "client_secret")
    flow_id, node_id, field_name = parse_autosecret_marker(marker)
    assert node_id == "Some_Node-1"
    assert field_name == "client_secret"


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "not-an-autosecret",
        "__autosecret_old-style",  # legacy underscore form — caller must use LEGACY_AUTOSECRET_PREFIX path
        "__autosecret|too|few",
        f"__autosecret|{FLOW_ID}|node",
        f"__autosecret|not-a-uuid|node|field",
    ],
)
def test_parse_rejects_malformed(bad):
    with pytest.raises(ValueError):
        parse_autosecret_marker(bad)
```

- [ ] **Step 2: Run tests to confirm fail**

```
uv run pytest src/backend/tests/unit/services/variable/test_marker.py -v
```
Expected: every test FAIL with `ImportError: cannot import name '...'` or `AttributeError`.

- [ ] **Step 3: Add constants + helpers to `auto_secrets.py`**

Edit `src/backend/base/langflow/services/variable/auto_secrets.py`. **Keep** the existing `AUTOSECRET_PREFIX`/`autosecret_flow_prefix`/`autosecret_name`/`_iter_promotable_fields` symbols for now (other code in this same file still uses them through Task 4 — they get rewritten then). Add new symbols below the existing ones:

```python
LEGACY_AUTOSECRET_PREFIX = "__autosecret_"
AUTOSECRET_DELIM = "|"


def autosecret_marker(flow_id: UUID, node_id: str, field_name: str) -> str:
    """Build the marker stored in `field["value"]` for an autosecret-backed field."""
    return AUTOSECRET_DELIM.join(
        ["__autosecret", str(flow_id), node_id, field_name]
    )


def autosecret_vault_path(
    org_id: UUID, flow_id: UUID, node_id: str, field_name: str
) -> str:
    """Vault KV v2 path for a per-field autosecret."""
    return f"{org_id}/flows/{flow_id}/autosecrets/{node_id}/{field_name}"


def parse_autosecret_marker(marker: str) -> tuple[UUID, str, str]:
    """Inverse of autosecret_marker.

    Raises ValueError on malformed input. Specifically rejects the legacy
    underscore-delimited prefix; callers should treat that prefix separately
    via LEGACY_AUTOSECRET_PREFIX.
    """
    if not isinstance(marker, str) or not marker.startswith("__autosecret" + AUTOSECRET_DELIM):
        msg = f"not an autosecret marker: {marker!r}"
        raise ValueError(msg)
    parts = marker.split(AUTOSECRET_DELIM)
    if len(parts) != 4:
        msg = f"autosecret marker has wrong segment count: {marker!r}"
        raise ValueError(msg)
    _prefix, flow_id_str, node_id, field_name = parts
    try:
        flow_id = UUID(flow_id_str)
    except ValueError as exc:
        msg = f"autosecret marker has invalid flow_id: {flow_id_str!r}"
        raise ValueError(msg) from exc
    if not node_id or not field_name:
        msg = f"autosecret marker has empty node_id or field_name: {marker!r}"
        raise ValueError(msg)
    return flow_id, node_id, field_name
```

`AUTOSECRET_PREFIX` itself flips from `__autosecret_` to `__autosecret|` — but **don't change it yet**. The existing `promote_plaintext_secrets_to_variables` and friends still rely on the old value. Task 4 will redefine `AUTOSECRET_PREFIX = "__autosecret|"` together with the function rewrite.

For Task 1 the test file uses the *new* prefix value. Add a sentinel module variable so the test can reference it without breaking the rest of the file's behavior:

```python
# Will replace AUTOSECRET_PREFIX in Task 4. Kept side-by-side until then.
NEW_AUTOSECRET_PREFIX = "__autosecret" + AUTOSECRET_DELIM
```

Update the test imports to read `NEW_AUTOSECRET_PREFIX as AUTOSECRET_PREFIX` so the assertions still pass:

```python
from langflow.services.variable.auto_secrets import (
    LEGACY_AUTOSECRET_PREFIX,
    NEW_AUTOSECRET_PREFIX as AUTOSECRET_PREFIX,
    autosecret_marker,
    autosecret_vault_path,
    parse_autosecret_marker,
)
```

(Task 4 swaps `NEW_AUTOSECRET_PREFIX` back to `AUTOSECRET_PREFIX` after the legacy code is gone.)

- [ ] **Step 4: Run tests to confirm pass**

```
uv run pytest src/backend/tests/unit/services/variable/test_marker.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Run the full auto_secrets test file to confirm no regression**

```
uv run pytest src/backend/tests/unit/services/variable/test_auto_secrets.py -v
```
Expected: PASS — existing tests untouched because the legacy `AUTOSECRET_PREFIX` and `autosecret_name` are still in place.

- [ ] **Step 6: Commit**

```bash
git add \
  src/backend/base/langflow/services/variable/auto_secrets.py \
  src/backend/tests/unit/services/variable/test_marker.py
git commit -m "$(cat <<'EOF'
feat(autosecrets): add Vault-aware marker + path helpers

Introduces autosecret_marker() (pipe-delimited so node ids and field names
can contain underscores), autosecret_vault_path(), parse_autosecret_marker(),
LEGACY_AUTOSECRET_PREFIX, and NEW_AUTOSECRET_PREFIX. Existing AUTOSECRET_PREFIX
is left in place; Task 4 of the migration plan swaps it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Org-id resolver helper

**Files:**
- Modify: `src/backend/base/langflow/services/variable/auto_secrets.py`
- Modify: `src/backend/tests/unit/services/variable/test_marker.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `src/backend/tests/unit/services/variable/test_marker.py`:

```python
import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.flow import Flow


@pytest.mark.asyncio
async def test_get_org_id_for_flow_returns_org(monkeypatch):
    from langflow.services.variable import auto_secrets

    org_id_value = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

    async def fake_exec(stmt):
        class _Result:
            def first(self_inner):
                return org_id_value
        return _Result()

    session = type("S", (), {"exec": fake_exec})()
    out = await auto_secrets._get_org_id_for_flow(FLOW_ID, session=session)
    assert out == org_id_value


@pytest.mark.asyncio
async def test_get_org_id_for_flow_missing_returns_none():
    from langflow.services.variable import auto_secrets

    async def fake_exec(stmt):
        class _Result:
            def first(self_inner):
                return None
        return _Result()

    session = type("S", (), {"exec": fake_exec})()
    out = await auto_secrets._get_org_id_for_flow(FLOW_ID, session=session)
    assert out is None
```

- [ ] **Step 2: Run, confirm fail**

```
uv run pytest src/backend/tests/unit/services/variable/test_marker.py::test_get_org_id_for_flow_returns_org src/backend/tests/unit/services/variable/test_marker.py::test_get_org_id_for_flow_missing_returns_none -v
```
Expected: FAIL — `_get_org_id_for_flow` doesn't exist yet.

- [ ] **Step 3: Add `_get_org_id_for_flow`**

In `auto_secrets.py`, near the top of the module (after the imports and constants):

```python
from sqlmodel import select


async def _get_org_id_for_flow(flow_id: UUID, *, session: AsyncSession) -> UUID | None:
    """Return the organization_id of the given flow, or None if the flow row is gone.

    Defensive: never raises. Callers fall through to a no-op when None is
    returned (treat as "flow no longer exists or untracked org").
    """
    from langflow.services.database.models.flow import Flow  # local import to avoid cycle

    stmt = select(Flow.organization_id).where(Flow.id == flow_id)
    result = await session.exec(stmt)
    return result.first()
```

If the existing imports already include `select` from sqlmodel, don't duplicate.

- [ ] **Step 4: Run, confirm pass**

```
uv run pytest src/backend/tests/unit/services/variable/test_marker.py -v
```
Expected: all marker tests PASS, including the two new ones.

- [ ] **Step 5: Commit**

```bash
git add \
  src/backend/base/langflow/services/variable/auto_secrets.py \
  src/backend/tests/unit/services/variable/test_marker.py
git commit -m "$(cat <<'EOF'
feat(autosecrets): add _get_org_id_for_flow helper

Single indexed lookup against flow.organization_id; returns None on missing
flow so callers can soft-fail (used by the upcoming Vault migration to
construct {org_id}/flows/{flow_id}/... paths).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `resolver.py` — dispatch by prefix

**Files:**
- Create: `src/backend/base/langflow/services/variable/resolver.py`
- Create: `src/backend/tests/unit/services/variable/test_resolver.py`

- [ ] **Step 1: Write the failing tests**

Create `src/backend/tests/unit/services/variable/test_resolver.py`:

```python
"""Tests for resolve_secret_reference dispatch."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from langflow.services.variable.auto_secrets import autosecret_marker, autosecret_vault_path


FLOW_ID = UUID("4312a8ac-22db-4d86-805e-86d19451c489")
ORG_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
NODE_ID = "ADPAuth-fMRCo"
FIELD_NAME = "client_secret"


@pytest.mark.asyncio
async def test_resolve_autosecret_returns_vault_value(monkeypatch):
    """A pipe-delimited autosecret marker resolves to the Vault payload's `value`."""
    from langflow.services.variable import resolver as resolver_mod

    secret_store = AsyncMock()
    secret_store.get = AsyncMock(return_value={"value": "the-secret"})

    async def fake_org_lookup(flow_id, *, session):
        return ORG_ID

    monkeypatch.setattr(resolver_mod, "_get_org_id_for_flow", fake_org_lookup)

    component = AsyncMock()  # not invoked for autosecret branch

    result = await resolver_mod.resolve_secret_reference(
        custom_component=component,
        name=autosecret_marker(FLOW_ID, NODE_ID, FIELD_NAME),
        field=FIELD_NAME,
        session=AsyncMock(),
        secret_store=secret_store,
    )
    assert result == "the-secret"
    secret_store.get.assert_awaited_once_with(
        autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, FIELD_NAME),
    )
    component.get_variable.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_autosecret_missing_payload_returns_empty(monkeypatch):
    from langflow.services.variable import resolver as resolver_mod

    secret_store = AsyncMock()
    secret_store.get = AsyncMock(return_value=None)

    async def fake_org_lookup(flow_id, *, session):
        return ORG_ID

    monkeypatch.setattr(resolver_mod, "_get_org_id_for_flow", fake_org_lookup)

    out = await resolver_mod.resolve_secret_reference(
        custom_component=AsyncMock(),
        name=autosecret_marker(FLOW_ID, NODE_ID, FIELD_NAME),
        field=FIELD_NAME,
        session=AsyncMock(),
        secret_store=secret_store,
    )
    assert out == ""


@pytest.mark.asyncio
async def test_resolve_autosecret_org_unresolvable_returns_empty(monkeypatch):
    """Foreign-flow marker (no matching flow row in this org) soft-fails to ''."""
    from langflow.services.variable import resolver as resolver_mod

    async def fake_org_lookup(flow_id, *, session):
        return None

    monkeypatch.setattr(resolver_mod, "_get_org_id_for_flow", fake_org_lookup)

    out = await resolver_mod.resolve_secret_reference(
        custom_component=AsyncMock(),
        name=autosecret_marker(FLOW_ID, NODE_ID, FIELD_NAME),
        field=FIELD_NAME,
        session=AsyncMock(),
        secret_store=AsyncMock(),
    )
    assert out == ""


@pytest.mark.asyncio
async def test_resolve_malformed_marker_returns_empty():
    """Manual JSON edits or partial migrations don't crash the build."""
    from langflow.services.variable import resolver as resolver_mod

    out = await resolver_mod.resolve_secret_reference(
        custom_component=AsyncMock(),
        name="__autosecret|garbage",
        field="x",
        session=AsyncMock(),
        secret_store=AsyncMock(),
    )
    assert out == ""


@pytest.mark.asyncio
async def test_resolve_non_autosecret_delegates_to_component():
    """User-managed Variable names defer to the component's existing get_variable path."""
    from langflow.services.variable import resolver as resolver_mod

    component = AsyncMock()
    component.get_variable = AsyncMock(return_value="env-value")

    out = await resolver_mod.resolve_secret_reference(
        custom_component=component,
        name="OPENAI_API_KEY",
        field="api_key",
        session=AsyncMock(),
        secret_store=AsyncMock(),
    )
    assert out == "env-value"
    component.get_variable.assert_awaited_once_with(
        name="OPENAI_API_KEY", field="api_key", session=AsyncMock.ANY,
    )
```

The last test uses `AsyncMock.ANY` as a sentinel for the session — the assertion only cares that the component was called, not which exact session object. If pytest complains about `AsyncMock.ANY`, replace with `mock.ANY` (`from unittest import mock`).

- [ ] **Step 2: Run, confirm fail**

```
uv run pytest src/backend/tests/unit/services/variable/test_resolver.py -v
```
Expected: FAIL — `resolver` module doesn't exist.

- [ ] **Step 3: Implement the resolver**

Create `src/backend/base/langflow/services/variable/resolver.py`:

```python
"""Dispatch helper for ``load_from_db`` field resolution.

Routes autosecret markers to Vault (per the new migration) and everything
else to the component's existing ``get_variable`` path (which itself layers
request-context overrides and the user-managed Variable service).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger

from langflow.services.variable.auto_secrets import (
    NEW_AUTOSECRET_PREFIX,
    _get_org_id_for_flow,
    autosecret_vault_path,
    parse_autosecret_marker,
)

if TYPE_CHECKING:
    from lfx.services.secret_store.base import SecretStore
    from sqlalchemy.ext.asyncio import AsyncSession


async def resolve_secret_reference(
    *,
    custom_component,
    name: str,
    field: str,
    session: AsyncSession,
    secret_store: SecretStore,
) -> str:
    """Resolve a ``load_from_db`` reference to its plaintext value.

    Returns ``""`` for autosecret markers whose Vault path doesn't exist
    (foreign-flow marker, deleted flow, or malformed input). The component's
    own required-field validation runs after and produces a user-visible
    error in that case.

    Non-autosecret names defer to ``custom_component.get_variable``, which
    keeps the existing behavior for request-context overrides and
    user-managed Variables.
    """
    if isinstance(name, str) and name.startswith(NEW_AUTOSECRET_PREFIX):
        return await _resolve_autosecret(name=name, session=session, secret_store=secret_store)
    return await custom_component.get_variable(name=name, field=field, session=session)


async def _resolve_autosecret(
    *, name: str, session: AsyncSession, secret_store: SecretStore,
) -> str:
    try:
        flow_id, node_id, field_name = parse_autosecret_marker(name)
    except ValueError as exc:
        await logger.adebug(f"malformed autosecret marker: {exc}")
        return ""

    org_id = await _get_org_id_for_flow(flow_id, session=session)
    if org_id is None:
        await logger.adebug(f"autosecret marker references unknown flow: {flow_id}")
        return ""

    path = autosecret_vault_path(org_id, flow_id, node_id, field_name)
    payload = await secret_store.get(path)
    if not payload:
        await logger.adebug(f"autosecret missing in Vault at {path}")
        return ""
    return payload.get("value") or ""
```

- [ ] **Step 4: Run, confirm pass**

```
uv run pytest src/backend/tests/unit/services/variable/test_resolver.py -v
```
Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add \
  src/backend/base/langflow/services/variable/resolver.py \
  src/backend/tests/unit/services/variable/test_resolver.py
git commit -m "$(cat <<'EOF'
feat(autosecrets): add resolver that dispatches load_from_db by prefix

resolve_secret_reference() routes pipe-delimited autosecret markers to
Vault (returning '' on miss for soft-fail validation UX) and defers all
other names to custom_component.get_variable(), preserving the existing
request-context and user-managed Variable behavior.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Rewrite `promote_plaintext_secrets_to_variables` to use Vault

**Files:**
- Modify: `src/backend/base/langflow/services/variable/auto_secrets.py`
- Modify: `src/backend/tests/unit/services/variable/test_auto_secrets.py`

- [ ] **Step 1: Rewrite `test_auto_secrets.py` to drive the new signature**

Replace the contents of `src/backend/tests/unit/services/variable/test_auto_secrets.py` with:

```python
"""Tests for autosecret lifecycle helpers (Vault-backed)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from lfx.services.secret_store.factory import InMemorySecretStore
from langflow.services.variable.auto_secrets import (
    LEGACY_AUTOSECRET_PREFIX,
    NEW_AUTOSECRET_PREFIX as AUTOSECRET_PREFIX,
    autosecret_marker,
    autosecret_vault_path,
    promote_plaintext_secrets_to_variables,
)


USER_ID = uuid4()
FLOW_ID = UUID("4312a8ac-22db-4d86-805e-86d19451c489")
ORG_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
NODE_ID = "APIRequest-abc123"


def _flow_data(field_template: dict, *, field_name: str = "cert_pem") -> dict:
    """Build a minimal flow `data` dict with one node + one templated field."""
    return {
        "nodes": [
            {
                "id": NODE_ID,
                "data": {
                    "node": {
                        "template": {
                            field_name: field_template,
                        },
                    },
                },
            }
        ],
        "edges": [],
    }


@pytest.fixture
def patched_org_lookup():
    with patch(
        "langflow.services.variable.auto_secrets._get_org_id_for_flow",
        return_value=ORG_ID,
    ) as patched:
        yield patched


@pytest.mark.asyncio
async def test_promote_writes_plaintext_to_vault(patched_org_lookup):
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": "-----BEGIN CERTIFICATE-----\nAAA\n-----END CERTIFICATE-----\n",
            "load_from_db": False,
        }
    )
    secret_store = InMemorySecretStore()
    variable_service = AsyncMock()
    variable_service.has_user_managed_variable = AsyncMock(return_value=False)

    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        secret_store=secret_store,
        variable_service=variable_service,
        session=AsyncMock(),
    )

    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert field["value"] == autosecret_marker(FLOW_ID, NODE_ID, "cert_pem")
    assert field["load_from_db"] is True

    stored = await secret_store.get(autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "cert_pem"))
    assert stored == {"value": "-----BEGIN CERTIFICATE-----\nAAA\n-----END CERTIFICATE-----\n"}


@pytest.mark.asyncio
async def test_promote_empty_value_with_existing_secret_preserves_marker(patched_org_lookup):
    """Issue 1 fix: empty value next to an existing Vault secret = 'untouched'."""
    secret_store = InMemorySecretStore()
    path = autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "cert_pem")
    await secret_store.put(path, {"value": "previously-saved-secret"})

    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": "",
            "load_from_db": True,
        }
    )

    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        secret_store=secret_store,
        variable_service=AsyncMock(),
        session=AsyncMock(),
    )

    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert field["value"] == autosecret_marker(FLOW_ID, NODE_ID, "cert_pem")
    assert field["load_from_db"] is True
    # Vault entry not modified
    assert (await secret_store.get(path))["value"] == "previously-saved-secret"


@pytest.mark.asyncio
async def test_promote_empty_value_with_no_secret_clears_field(patched_org_lookup):
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": "",
            "load_from_db": True,
        }
    )
    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        secret_store=InMemorySecretStore(),
        variable_service=AsyncMock(),
        session=AsyncMock(),
    )
    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert field["value"] == ""
    assert field["load_from_db"] is False


@pytest.mark.asyncio
async def test_promote_existing_marker_passes_through(patched_org_lookup):
    marker = autosecret_marker(FLOW_ID, NODE_ID, "cert_pem")
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": marker,
            "load_from_db": True,
        }
    )

    secret_store = InMemorySecretStore()
    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        secret_store=secret_store,
        variable_service=AsyncMock(),
        session=AsyncMock(),
    )
    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert field["value"] == marker
    # No write should have occurred for a passthrough.
    path = autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "cert_pem")
    assert await secret_store.get(path) is None


@pytest.mark.asyncio
async def test_promote_legacy_marker_clears_field(patched_org_lookup):
    """Dev-data hygiene: legacy underscore-delimited markers reset to empty."""
    legacy = LEGACY_AUTOSECRET_PREFIX + f"{FLOW_ID}_{NODE_ID}_cert_pem"
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": legacy,
            "load_from_db": True,
        }
    )
    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        secret_store=InMemorySecretStore(),
        variable_service=AsyncMock(),
        session=AsyncMock(),
    )
    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert field["value"] == ""
    assert field["load_from_db"] is False


@pytest.mark.asyncio
async def test_promote_user_managed_variable_name_passes_through(patched_org_lookup):
    flow_data = _flow_data(
        {
            "_input_type": "SecretStrInput",
            "auto_promote": True,
            "value": "OPENAI_API_KEY",
            "load_from_db": True,
        },
        field_name="api_key",
    )

    variable_service = AsyncMock()
    variable_service.has_user_managed_variable = AsyncMock(return_value=True)

    secret_store = InMemorySecretStore()
    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        secret_store=secret_store,
        variable_service=variable_service,
        session=AsyncMock(),
    )
    field = out["nodes"][0]["data"]["node"]["template"]["api_key"]
    assert field["value"] == "OPENAI_API_KEY"
    # Nothing written to Vault.
    assert await secret_store.list(f"{ORG_ID}/flows/") == []


@pytest.mark.asyncio
async def test_promote_skips_when_org_missing():
    """Defensive: missing flow row → no-op, don't crash the save."""
    flow_data = _flow_data(
        {
            "_input_type": "SecretStrInput",
            "auto_promote": True,
            "value": "plaintext",
            "load_from_db": False,
        }
    )
    with patch(
        "langflow.services.variable.auto_secrets._get_org_id_for_flow",
        return_value=None,
    ):
        out = await promote_plaintext_secrets_to_variables(
            flow_data=flow_data,
            flow_id=FLOW_ID,
            user_id=USER_ID,
            secret_store=InMemorySecretStore(),
            variable_service=AsyncMock(),
            session=AsyncMock(),
        )
    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    # Field untouched, plaintext stays — surface as a normal save failure
    # downstream rather than silently dropping the cred.
    assert field["value"] == "plaintext"
```

- [ ] **Step 2: Run, confirm fail**

```
uv run pytest src/backend/tests/unit/services/variable/test_auto_secrets.py -v
```
Expected: FAIL — function still has the old `variable_service`-only signature; `secret_store` kwarg unknown.

- [ ] **Step 3: Rewrite `promote_plaintext_secrets_to_variables`**

In `src/backend/base/langflow/services/variable/auto_secrets.py`:

3a. Rename the prefix constants. Replace:

```python
AUTOSECRET_PREFIX = "__autosecret_"
```

with:

```python
AUTOSECRET_PREFIX = "__autosecret|"
NEW_AUTOSECRET_PREFIX = AUTOSECRET_PREFIX  # retained alias for the resolver import
```

(Task 3 imported `NEW_AUTOSECRET_PREFIX`. After this swap they point at the same string.)

3b. Update the type-checking imports at the top to add `SecretStore`:

```python
if TYPE_CHECKING:
    from lfx.services.secret_store.base import SecretStore
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.variable.service import VariableService  # already there
```

3c. Replace the body of `promote_plaintext_secrets_to_variables` with:

```python
async def promote_plaintext_secrets_to_variables(
    *,
    flow_data: dict,
    flow_id: UUID,
    user_id: UUID,
    secret_store: SecretStore,
    variable_service: VariableService,
    session: AsyncSession,
) -> dict:
    """Walk a flow's template, promote plaintext secrets into Vault, and
    rewrite the field to reference the value via a stable marker.

    Branches:
      1. Empty value, no Vault secret existing → clean save (clear the field).
      2. Empty value, Vault secret exists → preserve marker (Issue 1 fix).
      3. Already a current-format autosecret marker → passthrough.
      3b. Legacy underscore-delimited marker → clear (dev-data hygiene).
      4. User-picked user-managed Variable name → passthrough.
      5. Typed-in plaintext → write Vault, point field at marker.
    """
    org_id = await _get_org_id_for_flow(flow_id, session=session)
    if org_id is None:
        # Flow row missing or org unresolvable; no-op so downstream surfaces
        # the real save error instead of silently dropping creds.
        return flow_data

    for node_id, field_name, field in _iter_promotable_fields(flow_data):
        marker = autosecret_marker(flow_id, node_id, field_name)
        path = autosecret_vault_path(org_id, flow_id, node_id, field_name)
        value = field.get("value") or ""

        # Branch 1 + 2: empty value
        if not value:
            existing = await secret_store.get(path)
            if existing and existing.get("value"):
                # Issue 1 fix: user re-saved without retyping; preserve.
                field["value"] = marker
                field["load_from_db"] = True
            else:
                field["value"] = ""
                field["load_from_db"] = False
            continue

        # Branch 3: current-format marker
        if isinstance(value, str) and value.startswith(AUTOSECRET_PREFIX):
            continue

        # Branch 3b: legacy marker (dev-data hygiene; no prod data exists)
        if isinstance(value, str) and value.startswith(LEGACY_AUTOSECRET_PREFIX):
            field["value"] = ""
            field["load_from_db"] = False
            continue

        # Branch 4: user-picked user-managed Variable name
        if await variable_service.has_user_managed_variable(
            name=value, user_id=user_id, session=session,
        ):
            continue

        # Branch 5: typed-in plaintext
        await secret_store.put(path, {"value": value})
        field["value"] = marker
        field["load_from_db"] = True

    return flow_data
```

3d. **Delete** the now-unused legacy `autosecret_name` (the underscore-style helper). It's been replaced by `autosecret_marker` from Task 1. Grep to confirm nothing else references it inside `auto_secrets.py`:

```
rg "autosecret_name\b" src/backend/base/langflow/services/variable/auto_secrets.py
```

If matches remain (e.g. in `cleanup_orphaned_autosecrets`), defer the deletion until Task 5/6 rewrite those bodies. Acceptable to leave it for one task and remove it then.

- [ ] **Step 4: Run, confirm pass**

```
uv run pytest src/backend/tests/unit/services/variable/test_auto_secrets.py src/backend/tests/unit/services/variable/test_marker.py -v
```
Expected: all tests PASS (the constants in `test_marker.py` now point at the swapped value via the alias).

- [ ] **Step 5: Commit**

```bash
git add \
  src/backend/base/langflow/services/variable/auto_secrets.py \
  src/backend/tests/unit/services/variable/test_auto_secrets.py
git commit -m "$(cat <<'EOF'
feat(autosecrets): route promote() through Vault SecretStore

promote_plaintext_secrets_to_variables() now writes plaintext to Vault at
{org_id}/flows/{flow_id}/autosecrets/{node_id}/{field_name} (KV v2 single-key
{"value": ...} payload). Marker delimiter switches from "_" to "|" so node
ids and field names with underscores parse cleanly.

Bundles the Issue 1 round-trip fix: empty-value-on-resave with an existing
Vault secret preserves the marker instead of wiping it. Legacy
underscore-delimited markers from dev data are cleared (no prod data).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Rewrite `cleanup_orphaned_autosecrets` and `delete_autosecrets_for_flow`

**Files:**
- Modify: `src/backend/base/langflow/services/variable/auto_secrets.py`
- Modify: `src/backend/tests/unit/services/variable/test_auto_secrets.py` (extend)

- [ ] **Step 1: Append failing tests**

Append to `src/backend/tests/unit/services/variable/test_auto_secrets.py`:

```python
from langflow.services.variable.auto_secrets import (
    cleanup_orphaned_autosecrets,
    delete_autosecrets_for_flow,
)


@pytest.mark.asyncio
async def test_cleanup_removes_orphans_only(patched_org_lookup):
    secret_store = InMemorySecretStore()
    # Two existing entries — one is still in the template, one is orphaned.
    await secret_store.put(
        autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "cert_pem"),
        {"value": "still-here"},
    )
    await secret_store.put(
        autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "deleted_field"),
        {"value": "orphan"},
    )
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": autosecret_marker(FLOW_ID, NODE_ID, "cert_pem"),
            "load_from_db": True,
        }
    )

    await cleanup_orphaned_autosecrets(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        secret_store=secret_store,
        session=AsyncMock(),
    )

    assert (
        await secret_store.get(
            autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "cert_pem")
        )
    ) == {"value": "still-here"}
    assert (
        await secret_store.get(
            autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "deleted_field")
        )
    ) is None


@pytest.mark.asyncio
async def test_cleanup_no_op_when_org_missing():
    secret_store = InMemorySecretStore()
    await secret_store.put(
        autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "cert_pem"),
        {"value": "x"},
    )
    with patch(
        "langflow.services.variable.auto_secrets._get_org_id_for_flow",
        return_value=None,
    ):
        await cleanup_orphaned_autosecrets(
            flow_data=_flow_data({"_input_type": "TextFileSecretInput", "auto_promote": True, "value": ""}),
            flow_id=FLOW_ID,
            user_id=USER_ID,
            secret_store=secret_store,
            session=AsyncMock(),
        )
    # Nothing deleted.
    assert (
        await secret_store.get(
            autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "cert_pem")
        )
    ) is not None


@pytest.mark.asyncio
async def test_delete_removes_all_under_flow(patched_org_lookup):
    secret_store = InMemorySecretStore()
    await secret_store.put(
        autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "cert_pem"),
        {"value": "x"},
    )
    await secret_store.put(
        autosecret_vault_path(ORG_ID, FLOW_ID, "OtherNode", "client_id"),
        {"value": "y"},
    )
    # Different flow — should be untouched.
    OTHER_FLOW = uuid4()
    await secret_store.put(
        autosecret_vault_path(ORG_ID, OTHER_FLOW, "X", "f"),
        {"value": "z"},
    )

    await delete_autosecrets_for_flow(
        flow_id=FLOW_ID,
        user_id=USER_ID,
        secret_store=secret_store,
        session=AsyncMock(),
    )

    assert await secret_store.get(
        autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "cert_pem")
    ) is None
    assert await secret_store.get(
        autosecret_vault_path(ORG_ID, FLOW_ID, "OtherNode", "client_id")
    ) is None
    # Other flow untouched.
    assert (
        await secret_store.get(autosecret_vault_path(ORG_ID, OTHER_FLOW, "X", "f"))
    ) == {"value": "z"}
```

- [ ] **Step 2: Run, confirm fail**

```
uv run pytest src/backend/tests/unit/services/variable/test_auto_secrets.py -v
```
Expected: 3 new tests FAIL — both `cleanup_orphaned_autosecrets` and `delete_autosecrets_for_flow` still have the old `variable_service` signature.

- [ ] **Step 3: Replace both function bodies**

In `src/backend/base/langflow/services/variable/auto_secrets.py`, replace `cleanup_orphaned_autosecrets` and `delete_autosecrets_for_flow` with:

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
        node_id = node_entry.rstrip("/")
        for field_entry in await secret_store.list(f"{base}{node_id}/"):
            field_name = field_entry.rstrip("/")
            existing.add((node_id, field_name))

    current = {(node_id, field_name) for node_id, field_name, _ in _iter_promotable_fields(flow_data)}

    for node_id, field_name in existing - current:
        await secret_store.delete(f"{base}{node_id}/{field_name}")


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
        node_id = node_entry.rstrip("/")
        for field_entry in await secret_store.list(f"{base}{node_id}/"):
            field_name = field_entry.rstrip("/")
            await secret_store.delete(f"{base}{node_id}/{field_name}")
```

- [ ] **Step 4: Run, confirm pass**

```
uv run pytest src/backend/tests/unit/services/variable/test_auto_secrets.py -v
```
Expected: all 10 tests PASS (7 from Task 4 + 3 new).

- [ ] **Step 5: Commit**

```bash
git add \
  src/backend/base/langflow/services/variable/auto_secrets.py \
  src/backend/tests/unit/services/variable/test_auto_secrets.py
git commit -m "$(cat <<'EOF'
feat(autosecrets): route cleanup + delete through Vault

cleanup_orphaned_autosecrets() and delete_autosecrets_for_flow() now walk
{org_id}/flows/{flow_id}/autosecrets/ in Vault (two-level KV v2 list) and
delete entries by path. No-op when the flow row is gone (org_id None) so
broken state surfaces upstream rather than crashing.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Wire resolver into `loading.py` + endpoint call sites

**Files:**
- Modify: `src/backend/base/langflow/interface/initialize/loading.py`
- Modify: `src/backend/base/langflow/api/v1/flows.py`

- [ ] **Step 1: Update `update_params_with_load_from_db_fields` to use the resolver**

In `src/backend/base/langflow/interface/initialize/loading.py`, replace lines 111-144 (the existing `update_params_with_load_from_db_fields` function) with:

```python
async def update_params_with_load_from_db_fields(
    custom_component: Component,
    params,
    load_from_db_fields,
    *,
    fallback_to_env_vars=False,
):
    from lfx.services.deps import get_secret_store
    from langflow.services.variable.resolver import resolve_secret_reference

    secret_store = get_secret_store()

    async with session_scope() as session:
        for field in load_from_db_fields:
            if field not in params or not params[field]:
                continue

            try:
                key = await resolve_secret_reference(
                    custom_component=custom_component,
                    name=params[field],
                    field=field,
                    session=session,
                    secret_store=secret_store,
                )
            except ValueError as e:
                if "User id is not set" in str(e):
                    raise
                if "variable not found." in str(e) and not fallback_to_env_vars:
                    raise
                await logger.adebug(str(e))
                key = None

            if fallback_to_env_vars and not key:
                key = os.getenv(params[field])
                if key:
                    await logger.ainfo(f"Using environment variable {params[field]} for {field}")
                else:
                    await logger.aerror(f"Environment variable {params[field]} is not set.")

            params[field] = key if key is not None else None
            if not key:
                await logger.awarning(f"Could not get value for {field}. Setting it to None.")

        return params
```

The semantic change: `key` returned from the resolver may be `""` for a missing autosecret (soft-fail). The fallback-to-env-vars and "Could not get value" logging now treats both `None` and `""` as missing (`not key`).

- [ ] **Step 2: Update flows.py call site at line 418 (create flow)**

```python
# Before
flow.data = await promote_plaintext_secrets_to_variables(
    flow_data=flow.data,
    flow_id=flow_id,
    user_id=current_user.id,
    variable_service=get_variable_service(),
    session=session,
)
```

```python
# After
flow.data = await promote_plaintext_secrets_to_variables(
    flow_data=flow.data,
    flow_id=flow_id,
    user_id=current_user.id,
    secret_store=get_secret_store(),
    variable_service=get_variable_service(),
    session=session,
)
```

Add the import at the top of `flows.py` next to other lfx-services imports:

```python
from lfx.services.deps import get_secret_store
```

- [ ] **Step 3: Update flows.py call sites at lines 611-624 (update flow)**

```python
# Before
var_svc = get_variable_service()
update_data["data"] = await promote_plaintext_secrets_to_variables(
    flow_data=update_data["data"],
    flow_id=db_flow.id,
    user_id=current_user.id,
    variable_service=var_svc,
    session=session,
)
await cleanup_orphaned_autosecrets(
    flow_data=update_data["data"],
    flow_id=db_flow.id,
    user_id=current_user.id,
    variable_service=var_svc,
    session=session,
)
```

```python
# After
var_svc = get_variable_service()
sec_store = get_secret_store()
update_data["data"] = await promote_plaintext_secrets_to_variables(
    flow_data=update_data["data"],
    flow_id=db_flow.id,
    user_id=current_user.id,
    secret_store=sec_store,
    variable_service=var_svc,
    session=session,
)
await cleanup_orphaned_autosecrets(
    flow_data=update_data["data"],
    flow_id=db_flow.id,
    user_id=current_user.id,
    secret_store=sec_store,
    session=session,
)
```

- [ ] **Step 4: Update flows.py call site at line 900 (delete flow)**

```python
# Before
await delete_autosecrets_for_flow(
    flow_id=flow.id,
    user_id=current_user.id,
    variable_service=get_variable_service(),
    session=session,
)
```

```python
# After
await delete_autosecrets_for_flow(
    flow_id=flow.id,
    user_id=current_user.id,
    secret_store=get_secret_store(),
    session=session,
)
```

- [ ] **Step 5: Run the relevant tests**

```
uv run pytest src/backend/tests/unit/services/variable -v
```
Expected: PASS — Task 4-5 tests still green; loading.py change has no dedicated tests but is type-checked by callers.

- [ ] **Step 6: Type-check sanity**

```
cd src/backend && uv run mypy base/langflow/api/v1/flows.py base/langflow/interface/initialize/loading.py base/langflow/services/variable/auto_secrets.py base/langflow/services/variable/resolver.py 2>&1 | head -20
```

If mypy isn't configured for these files (some langflow files have issues), instead run:

```
uv run python -c "from langflow.api.v1 import flows; from langflow.interface.initialize import loading; from langflow.services.variable import auto_secrets, resolver; print('ok')"
```

Expected: prints `ok`. If any import fails, fix the import path before continuing.

- [ ] **Step 7: Commit**

```bash
git add \
  src/backend/base/langflow/interface/initialize/loading.py \
  src/backend/base/langflow/api/v1/flows.py
git commit -m "$(cat <<'EOF'
feat(autosecrets): wire Vault resolver + secret_store into endpoints

update_params_with_load_from_db_fields now dispatches via
resolve_secret_reference, routing autosecret markers to Vault and
preserving the existing user-managed Variable / request-context override
behavior for everything else.

flows.py create/update/delete endpoints pass get_secret_store() into the
autosecret helpers alongside the existing variable_service.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Remove dead code in the Variable service

**Files:**
- Modify: `src/backend/base/langflow/services/variable/service.py`

- [ ] **Step 1: Confirm `list_autosecret_names_for_flow` has no remaining callers**

```
rg "list_autosecret_names_for_flow" src/backend src/lfx
```

Expected output: matches inside `service.py` itself (the definition) and the test for it (`test_has_user_managed_variable.py` if it covers it, or the legacy `test_auto_secrets.py` which we rewrote in Task 4 — those references should already be gone). If any production caller remains, STOP and ask — that's an unexpected use and the migration plan needs an addendum.

- [ ] **Step 2: Remove the method**

In `src/backend/base/langflow/services/variable/service.py`, delete the `list_autosecret_names_for_flow` method (around lines 422-442) and its test if one exists. Leave `has_user_managed_variable` in place — Task 4 still uses it for the dropdown branch.

- [ ] **Step 3: Run the variable-service tests**

```
uv run pytest src/backend/tests/unit/services/variable -v
```
Expected: all PASS. If a test for `list_autosecret_names_for_flow` exists in `test_service.py` or `test_has_user_managed_variable.py`, delete it.

- [ ] **Step 4: Commit**

```bash
git add src/backend/base/langflow/services/variable/service.py src/backend/tests/unit/services/variable/
git commit -m "$(cat <<'EOF'
chore(autosecrets): remove dead list_autosecret_names_for_flow

The Vault migration replaced the only caller (auto_secrets.py) with a
Vault-prefix list. has_user_managed_variable stays — still used by the
"user picked an existing Variable from a dropdown" branch.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Real-Vault integration test

**Files:**
- Create: `src/backend/tests/integration/services/test_autosecrets_vault.py`

This test mirrors `src/lfx/tests/integration/services/test_vault_secret_store.py` — gated on a real Vault dev-mode instance via the same env (`VAULT_ADDR`, `VAULT_TOKEN`, `LANGFLOW_SECRET_STORE_BACKEND=vault`). Run only when those are set.

- [ ] **Step 1: Create the integration test**

Create `src/backend/tests/integration/services/test_autosecrets_vault.py`:

```python
"""Integration tests for the autosecret Vault round-trip.

Gated on a real Vault dev-mode instance. Skipped when VAULT_ADDR is unset.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from lfx.services.secret_store.factory import get_secret_store
from lfx.services.secret_store.settings import SecretStoreSettings
from langflow.services.variable.auto_secrets import (
    autosecret_marker,
    autosecret_vault_path,
    cleanup_orphaned_autosecrets,
    delete_autosecrets_for_flow,
    promote_plaintext_secrets_to_variables,
)
from langflow.services.variable.resolver import resolve_secret_reference


pytestmark = pytest.mark.skipif(
    not os.environ.get("VAULT_ADDR") or not os.environ.get("VAULT_TOKEN"),
    reason="Vault integration tests require VAULT_ADDR and VAULT_TOKEN env vars",
)


@pytest.fixture
def vault_store():
    settings = SecretStoreSettings(
        SECRET_STORE_BACKEND="vault",
        VAULT_ADDR=os.environ["VAULT_ADDR"],
        VAULT_TOKEN=os.environ["VAULT_TOKEN"],
        VAULT_MOUNT_POINT=os.environ.get("VAULT_MOUNT_POINT", "secret"),
    )
    return get_secret_store(settings=settings)


@pytest.fixture
def org_id():
    return uuid4()


@pytest.fixture
def flow_id():
    return uuid4()


def _flow_data(value: str) -> dict:
    return {
        "nodes": [
            {
                "id": "ADPAuth-1",
                "data": {
                    "node": {
                        "template": {
                            "client_secret": {
                                "_input_type": "SecretStrInput",
                                "auto_promote": True,
                                "value": value,
                                "load_from_db": value == "" and False or True,
                            }
                        }
                    }
                },
            }
        ],
        "edges": [],
    }


@pytest.mark.asyncio
async def test_save_then_resolve_round_trip(vault_store, org_id, flow_id):
    user_id = uuid4()
    plaintext = "super-secret-cred-value"

    flow_data = _flow_data(plaintext)
    variable_service = AsyncMock()
    variable_service.has_user_managed_variable = AsyncMock(return_value=False)

    with patch(
        "langflow.services.variable.auto_secrets._get_org_id_for_flow",
        return_value=org_id,
    ):
        out = await promote_plaintext_secrets_to_variables(
            flow_data=flow_data,
            flow_id=flow_id,
            user_id=user_id,
            secret_store=vault_store,
            variable_service=variable_service,
            session=AsyncMock(),
        )

    field = out["nodes"][0]["data"]["node"]["template"]["client_secret"]
    marker = field["value"]
    assert marker == autosecret_marker(flow_id, "ADPAuth-1", "client_secret")

    # Resolve back through the prefix-dispatch path.
    component = AsyncMock()
    with patch(
        "langflow.services.variable.auto_secrets._get_org_id_for_flow",
        return_value=org_id,
    ):
        resolved = await resolve_secret_reference(
            custom_component=component,
            name=marker,
            field="client_secret",
            session=AsyncMock(),
            secret_store=vault_store,
        )

    assert resolved == plaintext

    # Cleanup
    await delete_autosecrets_for_flow(
        flow_id=flow_id,
        user_id=user_id,
        secret_store=vault_store,
        session=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_empty_resave_preserves_secret(vault_store, org_id, flow_id):
    """Issue 1 fix: real-Vault verification."""
    user_id = uuid4()
    plaintext = "round-1-cred"

    # First save
    with patch(
        "langflow.services.variable.auto_secrets._get_org_id_for_flow",
        return_value=org_id,
    ):
        first = await promote_plaintext_secrets_to_variables(
            flow_data=_flow_data(plaintext),
            flow_id=flow_id,
            user_id=user_id,
            secret_store=vault_store,
            variable_service=AsyncMock(),
            session=AsyncMock(),
        )
    marker = first["nodes"][0]["data"]["node"]["template"]["client_secret"]["value"]

    # Second save with empty value (simulating frontend round-trip)
    second_data = _flow_data("")
    with patch(
        "langflow.services.variable.auto_secrets._get_org_id_for_flow",
        return_value=org_id,
    ):
        second = await promote_plaintext_secrets_to_variables(
            flow_data=second_data,
            flow_id=flow_id,
            user_id=user_id,
            secret_store=vault_store,
            variable_service=AsyncMock(),
            session=AsyncMock(),
        )

    field = second["nodes"][0]["data"]["node"]["template"]["client_secret"]
    assert field["value"] == marker, "Expected marker preserved across empty re-save"
    assert field["load_from_db"] is True

    # Vault entry intact
    payload = await vault_store.get(
        autosecret_vault_path(org_id, flow_id, "ADPAuth-1", "client_secret")
    )
    assert payload == {"value": plaintext}

    # Cleanup
    await delete_autosecrets_for_flow(
        flow_id=flow_id,
        user_id=user_id,
        secret_store=vault_store,
        session=AsyncMock(),
    )
```

- [ ] **Step 2: Verify the test file is collected (without running it)**

```
uv run pytest src/backend/tests/integration/services/test_autosecrets_vault.py --collect-only -q
```
Expected: tests collected; if Vault env vars are unset, both will be skipped (not failed).

- [ ] **Step 3: Run the test against a real Vault if available**

If you have a local Vault dev mode running:

```
docker run -d --name=vault-dev -p 8200:8200 \
  -e VAULT_DEV_ROOT_TOKEN_ID=devroot \
  -e VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200 \
  hashicorp/vault:latest
```

Then:

```
VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=devroot \
  uv run pytest src/backend/tests/integration/services/test_autosecrets_vault.py -v
```

Expected: 2 PASS. If you don't have Vault locally, skip this step — the unit tests already cover the logic against `InMemorySecretStore`.

- [ ] **Step 4: Commit**

```bash
git add src/backend/tests/integration/services/test_autosecrets_vault.py
git commit -m "$(cat <<'EOF'
test(autosecrets): real-Vault round-trip + Issue 1 regression

Two integration tests gated on VAULT_ADDR/VAULT_TOKEN: end-to-end save →
resolve cycle, and the empty-value-on-resave preservation behavior. Skipped
in CI environments without Vault; runs locally against `vault dev` mode.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final verification

After all 8 tasks land, before declaring done:

- [ ] **Run the full variable-service unit suite:**
  ```
  uv run pytest src/backend/tests/unit/services/variable -v
  ```
  Expected: all green (Task 1+2+3 marker/resolver tests, Task 4+5 auto_secrets tests, Task 7 service tests).

- [ ] **Run the autosecret-lifecycle endpoint test:**
  ```
  uv run pytest src/backend/tests/unit/api/v1/test_flow_autosecret_lifecycle.py -v
  ```
  Expected: all green. If existing tests reference the old `variable_service`-only signatures, update them inline (this should already have shaken out via the test rewrites in Tasks 4-5, but the lifecycle tests were not listed in the spec because they're out-of-tree — verify here).

- [ ] **Run a smoke against the loading path:**
  ```
  uv run pytest src/backend/tests/unit/interface -v -k "load"
  ```
  Expected: existing loading tests still green; the resolver dispatch is transparent for non-autosecret names.

- [ ] **Wipe legacy dev autosecrets** (one-shot, not committed):
  ```
  docker exec postgresdb psql -U postgres -d langflow -c "DELETE FROM variable WHERE name LIKE '__autosecret\\_%' ESCAPE '\\\\';"
  ```
  Expected: rows deleted (matches the legacy `_`-delimited prefix). New writes go to Vault. The user reported flow `4312a8ac-22db-4d86-805e-86d19451c489` will start using Vault on next save.

- [ ] **Manual smoke test in the dev UI:**
  1. Open the flow `4312a8ac-22db-4d86-805e-86d19451c489`.
  2. Re-enter `client_id`, `client_secret`, `cert_pem`, `key_pem` on the ADP Auth node.
  3. Save the flow.
  4. Verify in Vault: `vault kv list secret/<org_id>/flows/4312a8ac-22db-4d86-805e-86d19451c489/autosecrets/` lists the four fields.
  5. Close and re-open the flow. Confirm fields appear masked-but-set, not blank.
  6. Save again WITHOUT retyping. Verify Vault entries are unchanged (`vault kv get` returns the original values).
  7. Run the flow. Confirm ADP auth succeeds (uses the resolved Vault values).

- [ ] **Skim the commit log:**
  ```
  git log --oneline -10
  ```
  Confirm 8 focused commits, no `git add -A` collateral, no amends.

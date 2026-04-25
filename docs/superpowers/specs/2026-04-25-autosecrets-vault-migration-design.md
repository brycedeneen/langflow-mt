# Auto-Secrets → Vault Migration

**Status:** Design complete, awaiting implementation plan
**Date:** 2026-04-25
**Branch:** `platform-multi-tenant`

## Goal

Migrate auto-promoted `SecretStrInput` / `TextFileSecretInput` field values from the Postgres `variable` table (Fernet-encrypted) to HashiCorp Vault via the existing `lfx.services.secret_store.SecretStore` interface. Bundle the Issue 1 round-trip fix so re-saving a flow without retyping a credential preserves it instead of orphaning the stored secret.

User-managed Variables (the global Variables UI: `OPENAI_API_KEY`-style entries created from `os.environ` and the UI) remain in Postgres unchanged.

## Background

Today the system has two parallel secret-storage paths:

| Path | Backend | Used for |
|---|---|---|
| `lfx.services.secret_store` (Vault) | HashiCorp Vault KV v2 | webhook auth keys, assistant API keys |
| `langflow.services.variable` (Postgres) | Postgres `variable` table, Fernet-encrypted | every `SecretStrInput`/`TextFileSecretInput` value, plus user-managed Variables |

`SECRET_STORE_BACKEND=vault` is the configured default but the auto-secret pipeline never went through it. The `auto_secrets.py` module promotes typed plaintext to a hidden `Variable` row named `__autosecret_<flow_id>_<node_id>_<field_name>` and points the field's `value` at that name with `load_from_db=True`. Per-org Vault would be the right home for these — it's purpose-built for credential storage with audit, rotation, and tenant isolation.

A second bug surfaced during investigation. When a user re-saves a flow without retyping a `SecretStrInput`, the frontend sends `value=""` for the masked field. `auto_secrets.py:97-100` interprets the empty value as "user cleared the field" and wipes both `value` and `load_from_db` — orphaning the encrypted credential and producing the symptom the user reported (ADP creds blank on reload). This spec bundles a defense-in-depth backend fix.

## Scope

**In scope:**
- `auto_secrets.py` — write/cleanup/delete go through `SecretStore` instead of `VariableService`.
- Runtime resolution (`update_params_with_load_from_db_fields` in `loading.py`) — discriminate by marker prefix, route Vault for autosecrets and Postgres for user-managed Variables.
- Issue 1 fix: empty-value-on-resave preserves the existing Vault secret instead of wiping the marker.
- Marker delimiter changed from `_` to `|` (no production data; this enables clean parsing).
- Tests rewritten/updated against `InMemorySecretStore` fixtures.

**Out of scope:**
- User-managed Variables (the global Variables UI). Stay in Postgres. A separate "B-split" spec migrates them later if desired.
- One-time migration of legacy Postgres autosecret rows. No production flows exist; dev rows can be wiped via SQL (`DELETE FROM variable WHERE name LIKE '__autosecret_%';`). Not a code task.
- Frontend changes. The marker still rides through the same `field.value`/`load_from_db` shape; the backend defense-in-depth fix removes the need to change the SecretStrInput display logic.
- Org-delete cascade for autosecrets. Vault has no FK; will need an explicit walker tied to the org-delete flow when that ships. Flagged as a follow-up.
- Save-path Vault perf optimization (batching gets via `list`). The current design issues one `Vault.get` per empty-value promotable field. For typical flows this is bounded (<10 calls). Revisit if p99 shows up.

## Architecture

```
                                      ┌─────────────────────────────┐
                                      │  POST /flows/{id}  (save)   │
                                      └──────────────┬──────────────┘
                                                     ▼
                              ┌──────────────────────────────────────────────┐
                              │ promote_plaintext_secrets_to_variables(...)  │
                              │  for each auto_promote=True field:           │
                              │    plaintext         → SecretStore.put       │
                              │    "" + Vault has it → preserve marker  ←────┼── ISSUE 1 FIX
                              │    "" + no Vault     → clean save (empty)    │
                              │    already a marker  → keep                  │
                              │    user-managed name → keep                  │
                              └──────────────────────────────────────────────┘
                                                     ▼
                                Vault (KV v2 mount = "secret"):
                                {org_id}/flows/{flow_id}/autosecrets/{node_id}/{field_name}
                                  payload: {"value": "<plaintext>"}

                                                ════════════════════
                                                later, on flow run
                                                ════════════════════

                                      ┌─────────────────────────────┐
                                      │   vertex.build()            │
                                      └──────────────┬──────────────┘
                                                     ▼
                              ┌──────────────────────────────────────────────┐
                              │ update_params_with_load_from_db_fields(...)  │
                              │  for each load_from_db=True field:           │
                              │    marker has __autosecret| prefix:          │
                              │       → resolver.SecretStore.get             │
                              │    otherwise:                                │
                              │       → variable_service.get_variable        │
                              └──────────────────────────────────────────────┘
```

Two new pieces, no new services:

1. **Adapter inside `auto_secrets.py`** that swaps Postgres calls for `SecretStore` calls. Existing public function signatures (`promote_plaintext_secrets_to_variables`, `cleanup_orphaned_autosecrets`, `delete_autosecrets_for_flow`, `blank_autosecrets_for_export`) keep their shape — call sites in `flows.py` only change which DI services they pass through.

2. **New resolver helper** at `src/backend/base/langflow/services/variable/resolver.py` that dispatches load_from_db lookups by prefix. Used by `update_params_with_load_from_db_fields`. One source of truth for the discrimination.

`SecretStore` and `VariableService` are both DI-registered today. No service-graph refactor.

## Data shape

### Marker format

```
__autosecret|<flow_id>|<node_id>|<field_name>
```

Stored in `field["value"]` next to `field["load_from_db"]=True`. The `|` delimiter replaces the legacy `_` delimiter so node ids and field names that contain `_` (e.g. `client_secret`) parse cleanly with `split("|")`. Constants:

```python
AUTOSECRET_PREFIX = "__autosecret|"  # was "__autosecret_"
AUTOSECRET_DELIM = "|"
LEGACY_AUTOSECRET_PREFIX = "__autosecret_"  # for transient dev-data hygiene; see Edge cases
```

### Vault path

```
{org_id}/flows/{flow_id}/autosecrets/{node_id}/{field_name}
```

Hierarchical, mirrors the existing webhook-auth convention (`{org_id}/webhooks/{flow_id}`). Lets `secret_store.list({org_id}/flows/{flow_id}/autosecrets/)` enumerate all autosecrets for a flow in two list calls (node ids, then field names within each node).

### Vault payload

```python
{"value": "<plaintext-secret>"}
```

Single-key dict. Field name, node id, flow id are all encoded in the path — payload stays minimal and round-trippable.

## The resolver

New module `src/backend/base/langflow/services/variable/resolver.py`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.services.variable.auto_secrets import (
    AUTOSECRET_PREFIX,
    parse_autosecret_marker,
    autosecret_vault_path,
)

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.services.secret_store.base import SecretStore
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.variable.base import VariableService


async def resolve_secret_reference(
    *,
    name: str,
    field: str,
    user_id: UUID,
    session: AsyncSession,
    secret_store: SecretStore,
    variable_service: VariableService,
) -> str:
    """Resolve a load_from_db reference to its plaintext value.

    Routes by marker prefix:
      - __autosecret|... → Vault (per-flow, org-scoped)
      - anything else    → VariableService (user-managed Postgres Variables)

    Returns "" when the autosecret cannot be found in Vault. The component's
    own required-field validation runs after and produces a user-friendly error.
    """
    if name.startswith(AUTOSECRET_PREFIX):
        return await _resolve_autosecret(name, session=session, secret_store=secret_store)
    return await variable_service.get_variable(
        user_id=user_id, name=name, field=field, session=session,
    )


async def _resolve_autosecret(
    name: str, *, session: AsyncSession, secret_store: SecretStore,
) -> str:
    try:
        flow_id, node_id, field_name = parse_autosecret_marker(name)
    except ValueError:
        return ""
    org_id = await _get_org_id_for_flow(flow_id, session=session)
    if org_id is None:
        return ""  # foreign-flow marker (imported from another flow); soft-fail
    payload = await secret_store.get(autosecret_vault_path(org_id, flow_id, node_id, field_name))
    if not payload:
        return ""
    return payload.get("value") or ""
```

`_get_org_id_for_flow(flow_id, session)` does one indexed SQL query against the `flow` table. Memoization is optional — for typical flows the extra queries are bounded (one per `load_from_db` field per build). If profiling shows it's hot, memoize via a small dict attribute on `AsyncSession` (`session._org_id_cache: dict[UUID, UUID]`) — implement only if measurements warrant.

## Write path (flow save)

`promote_plaintext_secrets_to_variables` body becomes:

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
    org_id = await _get_org_id_for_flow(flow_id, session=session)
    if org_id is None:
        # Defensive: flow row missing or org unresolvable; skip promotion entirely.
        return flow_data

    for node_id, field_name, field in _iter_promotable_fields(flow_data):
        marker = autosecret_marker(flow_id, node_id, field_name)
        path = autosecret_vault_path(org_id, flow_id, node_id, field_name)
        value = field.get("value") or ""

        # Branch 1+2: empty value
        if not value:
            existing = await secret_store.get(path)
            if existing and existing.get("value"):
                # Issue 1 fix: user saved without retyping; preserve reference.
                field["value"] = marker
                field["load_from_db"] = True
            else:
                field["value"] = ""
                field["load_from_db"] = False
            continue

        # Branch 3: already an autosecret marker (this flow's or a foreign one).
        if isinstance(value, str) and value.startswith(AUTOSECRET_PREFIX):
            continue

        # Branch 3-legacy: dev-era marker with the old "_" delimiter. Clear it
        # so the field reverts to empty; next typed plaintext promotes fresh.
        if isinstance(value, str) and value.startswith(LEGACY_AUTOSECRET_PREFIX):
            field["value"] = ""
            field["load_from_db"] = False
            continue

        # Branch 4: user picked a user-managed Variable name from a dropdown.
        if await variable_service.has_user_managed_variable(
            name=value, user_id=user_id, session=session,
        ):
            continue

        # Branch 5: typed-in plaintext — write to Vault, point field at marker.
        await secret_store.put(path, {"value": value})
        field["value"] = marker
        field["load_from_db"] = True

    return flow_data
```

Helper additions in `auto_secrets.py`:

- `autosecret_marker(flow_id, node_id, field_name) -> str` (renamed from `autosecret_name` for clarity).
- `autosecret_vault_path(org_id, flow_id, node_id, field_name) -> str`.
- `parse_autosecret_marker(marker) -> tuple[UUID, str, str]` (raises ValueError on bad input).

`_iter_promotable_fields` is unchanged.

## Read path (flow build)

`update_params_with_load_from_db_fields` in `src/backend/base/langflow/interface/initialize/loading.py` swaps a single line:

```python
# Before
value = await variable_service.get_variable(
    user_id=user_id, name=name, field=field, session=session,
)

# After
value = await resolve_secret_reference(
    name=name,
    field=field,
    user_id=user_id,
    session=session,
    secret_store=secret_store,
    variable_service=variable_service,
)
```

The function gains a `secret_store` parameter (DI-injected at the call site). All existing branches around the call (field-not-found handling, param replacement, error logging) stay unchanged.

## Lifecycle

### `cleanup_orphaned_autosecrets` — runs after every flow save

```python
async def cleanup_orphaned_autosecrets(
    *, flow_data, flow_id, user_id, secret_store, session,
) -> None:
    org_id = await _get_org_id_for_flow(flow_id, session=session)
    if org_id is None:
        return
    base = f"{org_id}/flows/{flow_id}/autosecrets/"
    existing: set[tuple[str, str]] = set()
    for node_id in await secret_store.list(base):
        node_id = node_id.rstrip("/")
        for field_name in await secret_store.list(f"{base}{node_id}/"):
            field_name = field_name.rstrip("/")
            existing.add((node_id, field_name))
    current = {(n, f) for n, f, _ in _iter_promotable_fields(flow_data)}
    for node_id, field_name in existing - current:
        await secret_store.delete(f"{base}{node_id}/{field_name}")
```

Two-level walk; KV v2 list returns immediate children with trailing slashes for directories.

### `delete_autosecrets_for_flow` — runs on flow delete

```python
async def delete_autosecrets_for_flow(
    *, flow_id, user_id, secret_store, session,
) -> None:
    org_id = await _get_org_id_for_flow(flow_id, session=session)
    if org_id is None:
        return
    base = f"{org_id}/flows/{flow_id}/autosecrets/"
    for node_id in await secret_store.list(base):
        node_id = node_id.rstrip("/")
        for field_name in await secret_store.list(f"{base}{node_id}/"):
            field_name = field_name.rstrip("/")
            await secret_store.delete(f"{base}{node_id}/{field_name}")
```

### `blank_autosecrets_for_export` — unchanged

Operates on the in-memory `flow_data` dict only. The marker prefix check still fires (now matching `__autosecret|` instead of `__autosecret_`). No code change.

## Edge cases

| Case | Behavior |
|---|---|
| User saves with empty `SecretStrInput`, no Vault secret exists | Clean save: `value=""`, `load_from_db=False`. |
| User saves with empty `SecretStrInput`, Vault secret already exists | **Issue 1 fix** — preserve marker; `load_from_db=True`; no Vault overwrite. |
| User saves with new plaintext over an existing Vault secret | `Vault.put` overwrites; KV v2 versioning kicks in (history not exposed). |
| User picks an existing user-managed Variable name from dropdown | Untouched — `has_user_managed_variable` check routes to Postgres path. |
| Flow imported from another org or copied (foreign marker, mismatched flow_id) | Read path: lookup misses → `""` → component's required-field validation fires. Next save promotes the user's retyped value into the current flow's path. |
| Field renamed/removed from a component's `inputs = [...]` | Post-save `cleanup_orphaned_autosecrets` walks Vault and deletes the orphan entry. |
| Flow deleted | `delete_autosecrets_for_flow` walks `{org_id}/flows/{flow_id}/autosecrets/` and deletes everything. |
| Flow exported | `blank_autosecrets_for_export` zeros JSON `value`; Vault entries untouched (still belong to source flow). Importer re-promotes on first save in destination. |
| Vault transiently unavailable on save | Save endpoint propagates the error (5xx); flow JSON does not persist with stale state. Same blast radius as a webhook-key save failure today. |
| Vault transiently unavailable on build | Resolver returns `""`; component required-field validation fires. The Vault error is logged so ops can correlate. |
| Foreign-flow marker (`flow_id` in marker doesn't match current flow) | Resolver looks up Vault path under the marker's `flow_id`; that path is under a different flow's tree, lookup returns `""`. Validation fires. Next save re-promotes. |
| Malformed marker (manual JSON edit, partial migration) | `parse_autosecret_marker` raises ValueError → resolver returns `""` → validation fires. |
| Legacy marker with old `_` delimiter (`__autosecret_<flow>_<node>_<field>`) in dev data | Treated as a clean-save: `_iter_promotable_fields` sees the value, no `__autosecret\|` prefix match, no user-managed match, but on the write path we add a sentinel check rejecting the legacy prefix as "already an autosecret-shaped marker — clear and let the user retype". Field becomes `value=""`, `load_from_db=False`; next time user types plaintext, fresh Vault write under the new format. No prod data exists; this is dev hygiene only. |

## Tests

### Unit tests (in-memory secret store)

**`test_auto_secrets.py` — rewritten:**
- `promote_plaintext_secrets_to_variables` exercises all 5 branches: empty+no-secret, empty+has-secret (Issue 1), already-marker, user-managed-name, plaintext-write.
- `cleanup_orphaned_autosecrets`: removes one field, asserts only that Vault path is deleted; adds a field, asserts no spurious deletes.
- `delete_autosecrets_for_flow`: deletes everything under the flow tree, asserts other flows' paths untouched.
- `blank_autosecrets_for_export`: regression — same behavior with `__autosecret|` prefix.

**`test_resolver.py` — new:**
- Autosecret prefix routes to `SecretStore`.
- Non-prefix name routes to `VariableService`.
- Missing Vault path returns `""`.
- Foreign-flow marker (`flow_id` not found in DB) returns `""`.
- Malformed marker returns `""` (no ValueError leak).
- Org-id resolution memoized (one SQL query for two same-flow lookups).

**`test_marker.py` — new:**
- `autosecret_marker` and `parse_autosecret_marker` round-trip.
- `parse_autosecret_marker` rejects malformed input (wrong prefix, wrong number of segments, non-UUID flow_id).

### Integration tests (real Vault, gated like existing `test_vault_secret_store.py`)

- Save → reload → resolve cycle for one ADP-Auth-style component, asserting plaintext is recovered.
- Save with empty value after first save preserves the secret (Issue 1).
- Flow delete removes Vault entries.
- Foreign-flow marker (simulate import) re-promotes on second save.

### Updated existing tests

- `src/backend/tests/unit/services/variable/test_auto_secrets.py` — replace Variable mocks with `InMemorySecretStore` fixtures.
- `src/backend/tests/unit/api/v1/test_flow_autosecret_lifecycle.py` — same.
- Any test asserting Postgres `Variable` rows for autosecret names — repointed to Vault.

## Files touched (summary)

**New:**
- `src/backend/base/langflow/services/variable/resolver.py` — dispatch helper.
- `src/backend/tests/unit/services/variable/test_resolver.py`.
- `src/backend/tests/unit/services/variable/test_marker.py`.
- (Optional) `src/backend/tests/integration/services/test_autosecrets_vault.py` — real-Vault round-trip.

**Modified:**
- `src/backend/base/langflow/services/variable/auto_secrets.py` — body changes in `promote_plaintext_secrets_to_variables`, `cleanup_orphaned_autosecrets`, `delete_autosecrets_for_flow` (3 of 4 functions). `blank_autosecrets_for_export` body is unchanged; only the prefix constant it references changes. New helpers: `autosecret_marker` (renamed from `autosecret_name`), `autosecret_vault_path`, `parse_autosecret_marker`. New constants: `AUTOSECRET_PREFIX = "__autosecret|"`, `LEGACY_AUTOSECRET_PREFIX = "__autosecret_"`.
- `src/backend/base/langflow/interface/initialize/loading.py` — `update_params_with_load_from_db_fields` calls the resolver instead of `variable_service.get_variable` directly; signature gains a `secret_store` parameter.
- `src/backend/base/langflow/api/v1/flows.py` — flow save and delete endpoints pass `secret_store` (DI) into the auto_secrets functions in addition to (or instead of) `variable_service`.
- `src/backend/base/langflow/services/flow/flow_runner.py` — if it calls into the read path, pass `secret_store` through.
- Test files listed in the Tests section.

**Removed (dead-code cleanup):**
- `src/backend/base/langflow/services/variable/service.py` — delete `list_autosecret_names_for_flow` (only `auto_secrets.py` used it; the Vault path doesn't need it). `has_user_managed_variable` stays (still used by the dropdown branch). Other Variable-service methods stay for user-managed Variables.

## Out of scope / follow-ups

- **User-managed Variables → Vault** (B-split). Separate spec when desired.
- **Org-delete cascade for autosecrets.** Vault has no FK; needs a walker tied to the org-delete flow.
- **Save-path Vault perf.** Current design issues one `Vault.get` per empty-value field. Could batch via a single `list` at the top. Easy follow-up if it shows up in p99.
- **Audit / rotation / lease UIs.** Vault gives us the data; no UI in this spec.
- **Legacy Postgres autosecret rows.** No production data; dev rows can be wiped with `DELETE FROM variable WHERE name LIKE '__autosecret_%';`. Not a code task.

# API Request mTLS — Vault-Backed Input (TextFileSecretInput)

**Date:** 2026-04-20
**Status:** Design
**Scope:** API Request component only (the just-cherry-picked mTLS feature)

## 1. Context

The API Request component recently gained mTLS support (branch `fork/feat/api-request-mtls-and-form-urlencoded`, cherry-picked onto `platform-multi-tenant` on 2026-04-20). That feature stores the client certificate and private key as uploaded files on the local filesystem via standard `FileInput`. Private keys in plaintext on disk is not acceptable for production.

Parallel observation: `ADPAuthComponent` already supports a "paste PEM" mode via `SecretStrInput(name="cert_pem")`, but that path does **not** use `load_from_db`, so those values sit plaintext in the flow's `data` JSON column. ADP Auth carries the same latent gap and is tracked for follow-up adoption.

This spec replaces the API Request component's file-on-disk mTLS fields with a new generic input type, `TextFileSecretInput`, backed by Langflow's existing Variable service (Fernet-encrypted in the DB). Users can either paste PEM content directly or drop a file; either way the content is stored encrypted at rest via an auto-created hidden Variable.

## 2. Goals

- **G1.** Private key material is Fernet-encrypted in the DB — never stored plaintext on disk or in the flow JSON.
- **G2.** No friction: user pastes or drops a file, flow saves, it just works. No separate "create a Variable first" step.
- **G3.** The input type is generic enough to reuse for other text-based credential files (SSH keys, GCP service account JSON, JWT files, API keys).
- **G4.** Existing Variable UI semantics (listed in Variables Manager, deletable, reusable across flows by name) remain intact for *user-managed* Variables. Auto-Variables are filtered out of that UI.

## 3. Non-goals

- Exporting secrets with flows (rejected during brainstorming: exports blank the value; user re-supplies on import).
- Duplicating a Variable reference across cloned flows (rejected: duplicate creates a fresh Variable so edits don't bleed through).
- Adopting `TextFileSecretInput` for `ADPAuthComponent` in this pass. Tracked as a follow-up.
- Storing actual binary files in Vault / Variables. Only text-readable files are supported.
- Running the integration tests against a real mTLS server (unit + mocked tests only).

## 4. Decisions captured from brainstorming

| # | Question | Answer |
|---|---|---|
| Q1 | Scope | API Request component only |
| Q2 | UX pattern | Tab toggle "Paste" / "Upload File" (same as ADP Auth's cert_source tab) |
| Q3 | Backward compat | Replace — remove `client_cert_file`, `client_key_file`; the feature is unreleased on this fork |
| Q4 | File → string conversion | Frontend `FileReader.readAsText()`; raw file bytes never touch backend disk |
| Q5 | Storage at rest | Auto-create hidden Variable (Fernet-encrypted), auto-set `load_from_db=true` |
| Q6 | Export / duplicate semantics | Export blanks the value; duplicate creates a fresh Variable |
| Name | Input type name | `TextFileSecretInput` |
| Type structure | Dedicated input type vs. extending `SecretStrInput` | Dedicated `TextFileSecretInput` subclass of `SecretStrInput` |

## 5. Architecture overview

Three new pieces:

1. **Backend input type** `TextFileSecretInput` — new class in `src/lfx/src/lfx/inputs/inputs.py`, extends `SecretStrInput`. Carries a `file_types: list[str]` parameter (e.g. `["pem", "crt", "key"]`). `_input_type = "TextFileSecretInput"` so the frontend can dispatch on it.

2. **Backend auto-Variable lifecycle** — new helpers in a new module (exact path TBD during implementation planning; likely `src/backend/base/langflow/services/variable/auto_secrets.py`) invoked from the flow save, delete, duplicate, export, and import endpoints.

3. **Frontend renderer** — new component that renders the tab-toggle UX when it sees `_input_type: "TextFileSecretInput"`. File tab uses `FileReader.readAsText()` client-side.

Plus the API Request component change:
- Remove: `client_cert_file` (FileInput), `client_key_file` (FileInput).
- Replace with: `cert_pem` (TextFileSecretInput), `key_pem` (TextFileSecretInput).
- Keep: `enable_mtls` (BoolInput), `client_key_password` (SecretStrInput with `load_from_db=True`).
- `update_build_config` continues to show/hide the cert/key/password fields based on `enable_mtls`.

## 6. Auto-Variable lifecycle (backend)

### 6.1 Variable naming

Auto-Variables use the prefix `__autosecret_` followed by `{flow_id}_{node_id}_{field_name}`. Example: `__autosecret_a734558b-8aa7-4ae3-948e-d02d98b8bc37_APIRequest-uhjld_cert_pem`.

### 6.2 Creation (on flow save)

New helper `promote_plaintext_secrets_to_variables(flow_data: dict, user_id: UUID, flow_id: UUID) -> dict` walks every node's template dict:

```
for each field in template:
    if field._input_type == "TextFileSecretInput"
       and field.value is a non-empty string
       and field.load_from_db is not True:
        variable_name = f"__autosecret_{flow_id}_{node_id}_{field_name}"
        upsert Variable(
            name=variable_name,
            value=field.value,
            type="CREDENTIAL",
            user_id=user_id,
        )
        field.value = variable_name
        field.load_from_db = True
return flow_data
```

Called inside the flow save endpoint (`POST /api/v1/flows`, `PATCH /api/v1/flows/{id}`) and the bulk import endpoint before `flow_data` is persisted. Upsert (not insert) so re-saves with the same value are idempotent, and edits update the Variable in place.

### 6.3 Update (on flow edit)

Frontend submits the new plaintext if the user changed the value in the editor (or uploaded a new file). Same `promote_plaintext_secrets_to_variables` walk catches it and upserts the Variable. If the user cleared the field, the promotion walker sees an empty value and calls `delete_autosecret(variable_name)`; see §6.4.

### 6.4 Deletion

Three deletion paths:

- **Node removed from flow:** after save, walk existing `__autosecret_{flow_id}_*` Variables, find any whose `node_id` no longer exists in the saved flow, delete them.
- **Flow deleted:** cascade via a pre-delete hook or an explicit `delete_autosecrets_for_flow(flow_id)` call inside the flow delete endpoint. Deletes all rows with name prefix `__autosecret_{flow_id}_`.
- **User deleted:** existing Variable cascade on user delete already handles this (Variables are `ON DELETE CASCADE` on `user_id`).

### 6.5 Duplication

Existing flow-clone endpoint returns a new flow with the same template values — meaning the cloned flow references the original's auto-Variables. A post-clone step resolves each `load_from_db=true` field whose value matches `__autosecret_{original_flow_id}_*`:

1. Fetch the original Variable's plaintext value.
2. Create a new Variable with the cloned flow's id in the name.
3. Rewrite the cloned flow's field value to the new Variable name.
4. Persist the cloned flow.

### 6.6 Export

In the flow export endpoint, before serialization, walk the template: for any field with `load_from_db=true` and a value matching the `__autosecret_{flow_id}_` prefix, blank the value (`""`) while leaving `load_from_db=true`. The exported JSON thus contains `{"value": "", "load_from_db": true}` for every auto-secret, signaling to the importer that a secret is expected but not bundled.

### 6.7 Import

Import reads a flow JSON that may contain `{"value": "", "load_from_db": true}` entries on `TextFileSecretInput` fields. Options:

- **Minimal (chosen default):** accept empty value. The component fails fast at run time with `ValueError("mTLS enabled but cert_pem is empty — paste or upload a certificate")`. Simple and explicit.
- **UX-nicer (future enhancement):** import dialog scans for empty secret fields and prompts the user to fill them before first save. Deferred — not in this spec's scope.

### 6.8 UI filtering

The Variables list endpoint (`GET /api/v1/variables`) excludes rows whose `name` starts with `__autosecret_`. Filtering at the backend (not the frontend) prevents auto-secret names from leaking via the API at all, including any future third-party UI or scripted use of the endpoint. Internal call sites that legitimately need to enumerate auto-Variables (e.g. cleanup, duplication) use a separate internal function that bypasses the filter.

## 7. Runtime flow

At vertex build time, the existing `update_params_with_load_from_db_fields` path resolves each `load_from_db=true` field via the Variable service and assigns the plaintext string to the component instance attribute. The API Request component therefore sees `self.cert_pem` and `self.key_pem` as plaintext PEM strings at `make_api_request` time.

### 7.1 Temp-file helper

New async context manager, extracted into a shared module so ADP Auth can adopt it later. Proposed location: `src/lfx/src/lfx/base/api_request/mtls.py`.

```python
@asynccontextmanager
async def mtls_temp_files(
    cert_pem: str | None,
    key_pem: str | None,
    key_password: str | None = None,
) -> AsyncIterator[tuple[str, str] | tuple[str, str, str] | None]:
    """Write PEM strings to 0600 temp files, yield httpx cert tuple, unlink on exit.

    Yields None if both cert_pem and key_pem are empty (no mTLS).
    Raises ValueError with a clear message on malformed PEM input.
    """
```

Implementation reuses the existing `_normalize_pem` and `_write_secure_tempfile` logic from `src/lfx/src/lfx/components/adp/_shared.py`, moving those helpers to the new module (and leaving thin re-exports in `adp/_shared.py` for no-op backward compat within the codebase). `mkstemp(suffix=".pem", prefix="langflow-mtls-")` creates files with 0600 perms; `unlink(missing_ok=True)` in a `finally` block with `suppress(OSError)` ensures cleanup runs on normal exit, exceptions, and `asyncio.CancelledError`.

### 7.2 Component call site

Inside `APIRequestComponent.make_api_request`:

```python
cert_pem = getattr(self, "cert_pem", None)
key_pem = getattr(self, "key_pem", None)
key_password = getattr(self, "client_key_password", None)

if getattr(self, "enable_mtls", False):
    if not (cert_pem and key_pem):
        raise ValueError(
            "Enable mTLS is on but cert_pem or key_pem is empty. "
            "Paste the PEM contents or upload a .pem file."
        )
    ctx = mtls_temp_files(cert_pem, key_pem, key_password)
else:
    ctx = mtls_temp_files(None, None, None)  # yields None

async with ctx as cert_tuple:
    async with httpx.AsyncClient(cert=cert_tuple) as client:
        result = await self.make_request(...)
```

### 7.3 Error surfaces

- `enable_mtls=True` with empty cert/key → `ValueError` before httpx init (explicit over the current silent `self.log`).
- Malformed PEM → wrap the `ssl.SSLError` from `httpx` / `ctx.load_cert_chain` in `ValueError` with the existing "include BEGIN/END lines, convert PKCS#12 first" hint (pattern from `adp/_shared.py:140-148`).
- Missing Variable (auto-Variable deleted out-of-band) → `update_params_with_load_from_db_fields` raises; component surfaces the error before httpx init.

### 7.4 Concurrency

`mkstemp` generates unique paths per call, so concurrent component runs don't collide. Each run owns its temp files and unlinks them.

## 8. Frontend contract

New renderer registered for `_input_type: "TextFileSecretInput"` in the component-node field render registry.

### 8.1 Layout

- Tab toggle at top of the field cell: `[Paste] [Upload File]`.
- **Paste tab:** standard SecretStrInput rendering — masked input (multiline if value contains newlines) with reveal toggle. Accepts paste.
- **Upload File tab:** drag-and-drop zone plus a file picker button. Accepts only files whose extension matches the field's `file_types` list. On selection:
  1. Reject if size > 1 MB (configurable constant — PEMs are a few KB).
  2. `FileReader.readAsText()` client-side.
  3. Write the string into the same backing `value` that the Paste tab uses.
  4. Discard the `File` object reference.
- The `File` object is never submitted to the backend. Only the resulting string is.

### 8.2 Shared value, ephemeral tab state

Both tabs write to one backing `value`. Switching tabs after setting a value preserves the value. The selected tab is ephemeral UI state (component-local React state), not persisted in the flow template. On flow reopen, default to Paste if `value` is non-empty; Upload if empty.

### 8.3 Soft validation

On successful file read (or on blur of the Paste tab), if the value does not start with `-----BEGIN ` or does not contain `-----END `, show a non-blocking warning banner: "Doesn't look like a PEM. Continue anyway if you're sure." Allow save — do not hard-block, since the field is generic and may accept other formats later.

### 8.4 Safety rails

- No `console.log` of the value anywhere in the renderer or its hooks.
- No `localStorage` or `sessionStorage` caching.
- On tab switch away from Upload, do not retain the `File` reference.
- `input[type=file]` element is reset (`value=""`) after read so selecting the same filename again re-triggers the change event.

## 9. API Request component migration

### 9.1 Field changes

Remove from `APIRequestComponent.inputs`:
- `FileInput(name="client_cert_file", ...)`
- `FileInput(name="client_key_file", ...)`

Add:
- `TextFileSecretInput(name="cert_pem", display_name="Client Certificate (PEM)", file_types=["pem", "crt"], advanced=True, show=False)`
- `TextFileSecretInput(name="key_pem", display_name="Client Key (PEM)", file_types=["pem", "key"], advanced=True, show=False)`

Keep unchanged:
- `BoolInput(name="enable_mtls", ...)` — toggles visibility of the below fields via `update_build_config`.
- `SecretStrInput(name="client_key_password", ...)` — already routes through Variables if `load_from_db=True`. Update it to `load_from_db=True` as part of this change.

### 9.2 `update_build_config` adjustments

When `enable_mtls` flips:
- Show/hide `cert_pem`, `key_pem`, `client_key_password` (mirrors the current logic, just renamed fields).

### 9.3 Starter projects

The `Pokédex Agent.json` starter project's `APIRequest` node carries the old field names. Migration updates its template to the new fields. Empty values are fine — starter project uses the API Request component but doesn't exercise mTLS.

### 9.4 Database migration

No DDL change. Variables table schema already supports the new rows. Pre-existing saved flows that used the old `client_cert_file` / `client_key_file` fields: on load, those fields will be absent from the component template and will be silently dropped from the node's saved template the next time the flow is saved (Langflow's standard behavior for removed fields). Uploaded cert files on disk become orphaned — out of scope for this spec; can be addressed in a separate cleanup task if desired.

## 10. Testing strategy

### 10.1 Backend unit — API Request component

Expand `src/backend/tests/unit/components/data_source/test_api_request_component.py`:

- `cert_pem` + `key_pem` strings → `mtls_temp_files` writes 2 × 0600 files → httpx receives `(cert_path, key_path)`.
- `cert_pem` + `key_pem` + `client_key_password` → httpx receives 3-tuple.
- Temp files are unlinked on normal exit, on raised exception inside `make_request`, and on `asyncio.CancelledError`.
- `enable_mtls=True` with empty `cert_pem` → `ValueError` raised before httpx is constructed.
- Malformed PEM string → `ValueError` with the "include BEGIN/END" hint.
- `_normalize_pem` roundtrip: `\n` literals and missing trailing newline are fixed before writing.

### 10.2 Backend unit — TextFileSecretInput

New `src/lfx/tests/unit/inputs/test_text_file_secret_input.py`:

- Class extends `SecretStrInput`.
- `_input_type == "TextFileSecretInput"` in serialized form.
- `file_types` round-trips through the template dict.

### 10.3 Backend integration — auto-Variable lifecycle

New `src/backend/tests/integration/test_auto_secrets.py` (or nearest existing integration test module):

- **Create:** POST a flow with `cert_pem="-----BEGIN CERTIFICATE----- ... -----END CERTIFICATE-----"` → DB has a new Variable with name `__autosecret_{flow_id}_{node_id}_cert_pem`; flow's saved `data` has `{value: "__autosecret_...", load_from_db: true}`.
- **Idempotent re-save:** save the same flow twice with the same value → exactly one Variable row, no duplicate.
- **Update:** save, then save again with a different PEM → Variable value is updated, still one row.
- **Clear:** save, then save with empty value → Variable deleted, field has empty value + `load_from_db=false`.
- **Node delete:** remove the APIRequest node, save → its `__autosecret_*` Variables are deleted.
- **Flow delete:** DELETE the flow → all `__autosecret_{flow_id}_*` Variables are deleted.
- **Duplicate:** clone the flow → new flow has fresh Variables with the clone's flow_id; original's Variables untouched.
- **Export:** GET the flow export → exported JSON has `{value: "", load_from_db: true}` for the mTLS fields; original flow unchanged.
- **Variables Manager filter:** GET `/api/v1/variables` does not return any name starting with `__autosecret_`.

### 10.4 Frontend

- Vitest component tests for `TextFileSecretInput` renderer: tab switch preserves value, file read populates value, oversize file is rejected, file extension filter works.
- Manual smoke in Chromium on the API Request node in a real flow: paste a PEM, save, verify encrypted Variable in DB, reload flow, verify value is masked in UI, run component against a local mTLS echo server.

### 10.5 Out of scope for test coverage

- Real-server mTLS handshake (relies on external infrastructure; covered by manual smoke).
- ADP Auth adoption — tracked as follow-up; that adoption will include its own tests.

## 11. Follow-ups (tracked, out of spec scope)

- **FU-1.** Adopt `TextFileSecretInput` for `ADPAuthComponent.cert_pem` / `key_pem` so ADP Auth also gets encryption at rest. Currently its PEMs sit plaintext in the flow JSON.
- **FU-2.** Import-time prompt for empty auto-secret fields (currently fails fast at run; a proactive prompt would improve UX).
- **FU-3.** Cleanup task for orphaned files on disk left behind by the old `client_cert_file` / `client_key_file` FileInputs before this migration.
- **FU-4.** Consider moving to real Hashicorp Vault (the `VaultSecretStore` exists in the codebase but is not wired to Variables) if/when we need key rotation, short-lived certs, or stronger isolation than Fernet-in-DB provides.

## 12. Risks

- **R1.** Auto-Variable naming collision across flows in the same user (unlikely: `{flow_id}_{node_id}_{field_name}` is unique per field instance). Upsert semantics handle the benign "re-save" case.
- **R2.** Orphan Variables if flow save fails after Variable creation but before flow persistence. Mitigation: perform the Variable upsert inside the same DB transaction as the flow save, or reconcile on flow read ("these autosecret names don't match any field in the saved flow — delete").
- **R3.** Client-side `FileReader` availability: all modern browsers support it; IE is not supported by Langflow.
- **R4.** Regression risk on the starter project `Pokédex Agent.json`: template regeneration during the migration may fight the concurrent pandas 3.0 session's Pokédex regen. Coordinate the merge.

## 13. Implementation plan

Out of scope for this spec. The implementation plan will be written next via the `superpowers:writing-plans` skill and saved to `docs/superpowers/plans/`.

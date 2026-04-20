# ADP Auth — TextFileSecretInput + Default-On Auto-Promotion

**Date:** 2026-04-20
**Status:** Design
**Scope:** `ADPAuthComponent` migration + cross-cutting default on `SecretStrInput.auto_promote`

## 1. Context

The preceding `TextFileSecretInput` feature (spec `2026-04-20-api-request-mtls-vault-backed-input-design.md`) landed `TextFileSecretInput` and an auto-Variable promotion lifecycle keyed on `_input_type == "TextFileSecretInput"`. Only the `APIRequest` component adopted it.

`ADPAuthComponent` still has two latent issues:

- Its `cert_pem` / `key_pem` fields are `SecretStrInput` without `load_from_db=True`, meaning pasted PEMs sit **plaintext in the flow JSON** on disk and in the DB.
- Its `client_id` / `client_secret` are also `SecretStrInput` without `load_from_db=True`, same plaintext issue.
- Its `cert_source` `TabInput` with "File Path" vs "PEM" modes is redundant — `TextFileSecretInput` subsumes both via paste-or-upload.

This spec migrates ADP Auth to the new input type **and** makes `auto_promote=True` the default on all `SecretStrInput` fields codebase-wide, so encryption-at-rest becomes the default behavior for every secret field in Langflow, not just TextFileSecretInput.

## 2. Goals

- **G1.** ADP Auth's cert/key/client-id/client-secret all become Fernet-encrypted in the DB via the existing auto-Variable lifecycle. No field of `ADPAuthComponent` stores plaintext credentials at rest.
- **G2.** `ADPAuthComponent` offers the same paste-or-upload UX for PEMs as `APIRequest` does.
- **G3.** Every `SecretStrInput` in the codebase automatically gains encryption-at-rest on next flow save, not just ADP Auth's. One cross-cutting default flip instead of per-component retrofit.
- **G4.** Component authors who need an explicit escape hatch can set `auto_promote=False` — supported but rarely needed.

## 3. Non-goals

- Migrating other components (OpenAI / Anthropic / HuggingFace / etc.) in this spec. They pick up the new default automatically without code changes, but their tests and starter projects are out of scope.
- Frontend polish to replace the fixed-length masked autosecret dots with a "Secret set — click to replace" affordance. Tracked as a follow-up, not blocking.
- Renaming `SecretStrInput` or introducing a new base class hierarchy.
- Changing the Variable service's storage backend (still Fernet-encrypted-in-DB; actual Hashicorp Vault adoption is a separate future discussion).

## 4. Decisions captured from brainstorming

| # | Question | Answer |
|---|---|---|
| Q1 | Fate of ADP Auth's "File Path" cert mode | **Remove entirely**. No prod flows use it; replace with `TextFileSecretInput` paste-or-upload. |
| Q2 | Scope: `client_id` / `client_secret` too? | **Include via generalized auto-promote.** Make `auto_promote=True` the default on `SecretStrInput`. These fields inherit the new default. |
| Q3 | `_shared.py` cleanup level | **Unify on shared primitive.** Call `mtls_temp_files` from `lfx.base.api_request.mtls` instead of keeping ADP-specific `_write_pem_temp_files`. |

## 5. Architecture overview

Three backend surfaces change:

1. **`SecretStrInput` gains `auto_promote: bool = True`** as a default-on class field in `src/lfx/src/lfx/inputs/inputs.py`. Subclasses including `TextFileSecretInput` inherit. Any component author can explicitly set `auto_promote=False` per field if the value needs plaintext round-trip.

2. **Auto-secrets helpers generalize** in `src/backend/base/langflow/services/variable/auto_secrets.py`. The per-field filter changes from "input type is TextFileSecretInput" to "field has `auto_promote=True`". All existing endpoint wiring is unchanged.

3. **`ADPAuthComponent` restructures** in `src/lfx/src/lfx/components/adp/adp_auth.py`:
   - Remove `cert_source`, `cert_path`, `key_path`.
   - Convert `cert_pem`, `key_pem` from `SecretStrInput` to `TextFileSecretInput` (paste-or-upload).
   - `client_id`, `client_secret` stay `SecretStrInput` and gain auto-promotion from the new default.
   - Add `version: int = 2` + `ChangelogEntry` with migration `notes`.
   - `ADPConnection` dataclass loses `cert_source`, `cert_path`, `key_path`.
   - `build_mtls_httpx_client` loses the path branch and delegates to `mtls_temp_files`.
   - `_write_pem_temp_files` and the ADP-specific `_MTLSClient` subclass are deleted.

## 6. Auto-promote logic (generalized)

### 6.1 New class field on SecretStrInput

```python
class SecretStrInput(BaseInputMixin, DatabaseLoadMixin):
    field_type = FieldTypes.PASSWORD
    password = True
    load_from_db = True
    track_in_telemetry = False

    auto_promote: bool = True
    """Whether typed-in plaintext values are automatically promoted to hidden
    auto-Variables on flow save. Default True. Set False for fields whose
    value needs plaintext round-trip through flow JSON (rare)."""
```

`TextFileSecretInput` inherits `auto_promote=True` by default. No explicit declaration needed there.

### 6.2 Walker generalization

`_iter_textfilesecret_fields` is renamed to `_iter_promotable_fields`. Predicate becomes:

```python
if field.get("auto_promote") is True:
    yield (node_id, field_name, field)
```

Input type is no longer consulted — the flag is the contract. Any field author can opt any field in or out via `auto_promote`.

### 6.3 User-managed-Variable detection

`SecretStrInput` with `load_from_db=True` permits two input modes on the frontend: type inline, or pick an existing Variable by name. Structurally both are strings; the backend can't distinguish by shape alone.

New method on `VariableService`:

```python
async def has_user_managed_variable(
    self, *, name: str, user_id: UUID, session: AsyncSession
) -> bool:
    """Return True if a user-managed Variable with this name exists for the
    user. Auto-secrets are excluded from the match."""
```

Implementation:

```sql
SELECT 1
FROM variable
WHERE user_id = :user_id
  AND name = :name
  AND name NOT LIKE '__autosecret_%'
LIMIT 1
```

Called by `promote_plaintext_secrets_to_variables` for each field with a non-empty non-autosecret value. If `True`, the field is preserved as a reference (no promotion). If `False`, the value is typed plaintext and is promoted.

### 6.4 Revised promote logic

For each promotable field with a non-empty value:

```
expected_name = autosecret_name(flow_id, node_id, field_name)

# Already an autosecret reference (idempotent path).
if value == expected_name and expected_name in existing_autosecret_names:
    continue

# Other autosecret names (e.g. copied from another flow). Treat as already
# promoted but pointing at a foreign Variable — leave alone. Spec R5.
if value.startswith(AUTOSECRET_PREFIX):
    continue

# User picked a user-managed Variable by name. Preserve the reference.
if await variable_service.has_user_managed_variable(
    name=value, user_id=user_id, session=session
):
    continue

# Otherwise: this is typed-in plaintext. Upsert the autosecret Variable.
if expected_name in existing_autosecret_names:
    await variable_service.update_variable_value(name=expected_name, value=value, ...)
else:
    await variable_service.create_variable(name=expected_name, value=value, ...)

field["value"] = expected_name
field["load_from_db"] = True
```

All existing helper contracts (`cleanup_orphaned_autosecrets`, `delete_autosecrets_for_flow`, `blank_autosecrets_for_export`) stay unchanged externally — they all consume the same walker, which now yields more fields.

## 7. ADPAuthComponent migration

### 7.1 Field changes

Remove:
- `cert_source: TabInput` with options `["File Path", "PEM"]`
- `cert_path: MessageTextInput`
- `key_path: MessageTextInput`

Convert in-place:
- `cert_pem: SecretStrInput` → `TextFileSecretInput(name="cert_pem", file_types=["pem", "crt"], display_name="Client Certificate (PEM)", info="...", advanced=False, required=True, show=True)`
- `key_pem: SecretStrInput` → `TextFileSecretInput(name="key_pem", file_types=["pem", "key"], display_name="Client Key (PEM)", info="...", advanced=False, required=True, show=True)`

Unchanged (inherit `auto_promote=True` from the new default):
- `client_id: SecretStrInput`
- `client_secret: SecretStrInput`
- `token_url: MessageTextInput`

### 7.2 `build_connection` method

The method body no longer branches on `cert_source`. Validation collapses to: cert_pem non-empty, key_pem non-empty, client_id non-empty, client_secret non-empty. `ADPConnection` is constructed from the four secret fields plus `token_url`.

### 7.3 `update_build_config`

Removes the `cert_source` branch entirely. The remaining logic reduces to nothing component-specific (no longer need to show/hide fields based on `cert_source`). The method may be deleted if no other field-visibility rules remain.

### 7.4 Version + changelog

```python
version: int = 2
changelog: ClassVar[list[ChangelogEntry]] = [
    ChangelogEntry(
        version=2,
        changes=(
            "- Replaced the `cert_source` File Path / PEM toggle with "
            "**paste-or-upload** TextFileSecretInput fields for cert_pem and "
            "key_pem.\n"
            "- `cert_path` and `key_path` inputs removed.\n"
            "- client_id, client_secret, cert_pem, and key_pem are now "
            "Fernet-encrypted at rest via hidden auto-Variables (not stored "
            "plaintext in the flow JSON)."
        ),
        notes=(
            "Saved flows with cert_source='File Path' drop the cert_path and "
            "key_path values on load. Paste the certificate and key PEMs "
            "(or upload the .pem / .crt / .key files) into the new fields to "
            "restore the connection. client_id and client_secret typed inline "
            "are now silently encrypted on save; if you previously saw "
            "plaintext values in exported flow JSON you will now see empty "
            "values — re-enter the credentials on import."
        ),
    ),
]
```

The changelog starts at v2 (not v1). Rationale: `ADPAuthComponent` predates the versioning infra and has no pre-existing changelog entries, so the implicit version before this change is v1. This PR's behavior changes bump to v2. No retroactive v1 entry is added — users had no changelog to read before, so there's nothing user-facing about v1 to document.

## 8. Shared module cleanup

`src/lfx/src/lfx/components/adp/_shared.py` simplifies:

### 8.1 `ADPConnection` dataclass

Remove fields: `cert_source: Literal["path", "pem"]`, `cert_path: str | None`, `key_path: str | None`. Keep: `cert_pem`, `key_pem`, `client_id`, `client_secret`, `api_base_url`, `mcp_base_url`, `token_url`, `access_token`, `token_expires_at`.

### 8.2 `build_mtls_httpx_client`

Collapses to a wrapper around `mtls_temp_files`:

```python
@asynccontextmanager
async def build_mtls_httpx_client(
    conn: ADPConnection, *, timeout: float = 30.0
) -> AsyncIterator[httpx.AsyncClient]:
    """Async context manager that yields an httpx.AsyncClient configured with
    mTLS built from the ADPConnection's PEMs."""
    from lfx.base.api_request.mtls import mtls_temp_files

    if not conn.cert_pem or not conn.key_pem:
        raise ValueError(
            "ADPConnection is missing cert_pem or key_pem. Both are required."
        )
    async with mtls_temp_files(conn.cert_pem, conn.key_pem) as cert_tuple:
        async with httpx.AsyncClient(cert=cert_tuple, timeout=timeout) as client:
            yield client
```

Shape change: was a plain callable returning a client, now an async context manager. Callers (`fetch_token`, consumers of the connection) need updating to use `async with build_mtls_httpx_client(conn) as client:`. The ADP API Request / MCP / worker-tool / trigger components already use this pattern — verify each call site before rename.

### 8.3 Deleted

- `_write_pem_temp_files` — replaced by `mtls_temp_files`.
- `_MTLSClient` subclass — its cleanup-on-close behavior is now covered by `mtls_temp_files`'s `finally` block.
- `_normalize_pem` and `_write_secure_tempfile` re-exports — no longer needed if no ADP-specific helper imports them. Keep the re-exports only if any external caller in-repo still references them (grep first).

## 9. Testing strategy

### 9.1 New unit tests

- `src/lfx/tests/unit/inputs/test_secret_str_input.py` — `auto_promote` default is `True`; subclasses inherit; explicit `auto_promote=False` overrides; serialization round-trip.
- `src/backend/tests/unit/services/variable/test_auto_secrets.py` — extend:
   - `_iter_promotable_fields` yields SecretStrInput + TextFileSecretInput equally when `auto_promote=True`.
   - `_iter_promotable_fields` skips fields with `auto_promote=False` regardless of input type.
   - `promote_*` skips fields whose value matches an existing user-managed Variable (uses the new `has_user_managed_variable`).
- `src/backend/tests/unit/services/variable/test_variable_service.py` — `has_user_managed_variable`: returns True for user-managed, False for autosecrets, False for missing, scoped to `user_id`.

### 9.2 Updated unit tests

- `src/lfx/tests/unit/components/adp/test_adp_auth.py`:
  - Delete all `cert_source="path"` scenarios, `cert_path`/`key_path` assertions.
  - Update remaining tests for `cert_pem`/`key_pem` as `TextFileSecretInput`.
  - Add tests: `client_id` / `client_secret` typed plaintext propagate to `ADPConnection` (at build_connection time, plaintext is visible in-process; the promote step only runs via the flow endpoint).
- `src/lfx/tests/unit/components/adp/test_shared.py`:
  - Drop path-mode `build_mtls_httpx_client` tests.
  - Update PEM-mode tests for the new async-context-manager shape.
  - Drop `_write_pem_temp_files` tests.
  - Keep `validate_adp_url`, `fetch_token` tests; update `fetch_token` to call `build_mtls_httpx_client` as a context manager.
- Other ADP component tests (`test_adp_api_request.py`, `test_adp_mcp.py`, `test_adp_worker_tools.py`, `test_adp_trigger.py`): update any that construct `ADPConnection` with `cert_source`/`cert_path`/`key_path` to use the new shape.

### 9.3 Integration tests

Extend `src/backend/tests/unit/api/v1/test_flow_autosecret_lifecycle.py`:
- Add a case POSTing a flow with a bare `SecretStrInput` field containing plaintext → autosecret Variable created, field rewritten with `load_from_db=True`. Proves the generalized walker works end-to-end.
- Add a case POSTing a flow where `SecretStrInput.value` is the name of a pre-existing user-managed Variable → field is NOT rewritten (user-picked reference preserved).

### 9.4 Manual smoke

After implementation: load each starter project flow, confirm JSON parses and component field shapes are valid. Run the starter regen script (`scripts/ci/update_starter_projects.py`) after the core changes land, commit any starter drift in a separate commit.

## 10. Cross-cutting rollout

Default `auto_promote=True` affects every existing `SecretStrInput` in the codebase. That's the intended security improvement, but it's a behavior change with audit surface:

### 10.1 What changes for those components on next flow save

- Pasted secrets promote to hidden Variables (transparent to users).
- Exported flows no longer contain plaintext secrets in the affected fields (correct behavior, previously broken).
- Frontend renderers continue to show masked dots (no UI change).
- Runtime `self.some_secret` access resolves the Variable at vertex build — same behavior as load_from_db has always supported.

### 10.2 Audit task in the spec, not in scope of implementation

- Run `grep -rn "SecretStrInput(" src/` to enumerate current SecretStrInput sites (expect 100+).
- For each, consider: does anything read `flow.data` JSON and expect plaintext in this field? Rare. Examples would be: automated scripts that parse exported flow JSON, CI tooling that extracts credentials from a flow for test runs. If yes, set `auto_promote=False` explicitly on that field.
- Default assumption: if nobody has a concrete reason, the new default-True behavior is correct.

### 10.3 Rollback

No feature flag. If a regression appears after rollout, `git revert` the single commit that changes the default on `SecretStrInput.auto_promote`. The promote helpers themselves already existed in a dormant state (guarded by `auto_promote`); reverting the default returns them to TextFileSecretInput-only scope.

### 10.4 Components with known call sites worth double-checking

Non-exhaustive list of components that will flip to auto-promote on next save:
- OpenAI / Anthropic / HuggingFace / Cohere / Azure / Google / Bedrock model components (api_key fields)
- Database connectors (connection strings, credentials)
- Vector store components (API keys / tokens)
- Webhook components (signing secrets)
- Assorted custom components that declare `SecretStrInput`

None of these have a known legitimate reason to keep plaintext round-trip. All will silently benefit.

## 11. Risks

- **R1. Overpromotion.** If `has_user_managed_variable` erroneously returns False for a user-managed Variable, a reference gets accidentally converted to an autosecret pointing at the Variable's name. Mitigation: the SELECT 1 query is simple and well-tested. Add a test that asserts the user-picked-Variable path is preserved.
- **R2. Starter project drift.** Starter projects serialize template dicts including `auto_promote`. Existing starters won't have the field present in their JSON. The auto-promote walker reads `field.get("auto_promote") is True` — `None` is not True, so missing flags are treated as False. Starters will inherit auto_promote=True only after a `scripts/ci/update_starter_projects.py` run regenerates them against the new default. Schedule that run after the core commit.
- **R3. Frontend UX gap.** Users editing a pre-existing autosecret see fixed-length masked dots with no "secret set" indicator. Functional but suboptimal. Tracked as follow-up, not blocking.
- **R4. Migration for existing flows with pre-feature `SecretStrInput` values.** On first save after the default flip, values promote to autosecrets. That's the intended behavior; no explicit migration step needed. Users may notice their exported flows stop carrying plaintext secrets — that's the correct outcome.
- **R5. Cross-flow-copied autosecret references.** If a user exports a flow and re-imports it, the autosecret names contain the original `flow_id`. The new importer doesn't have those Variables. The promote helper's "starts with AUTOSECRET_PREFIX" early exit preserves the reference as-is (to avoid accidentally re-wrapping), but the flow's next run fails with "Variable not found." Mitigation: the existing `blank_autosecrets_for_export` step zeros out these values on export, so importers always start with empty fields they need to refill. This is the existing designed behavior.

## 12. Follow-ups (tracked, out of scope)

- **FU-1.** Frontend renderer polish: show "Secret set — click to replace" affordance when value starts with `AUTOSECRET_PREFIX`, instead of raw masked dots. Applies to both TextFileSecretInput and SecretStrInput renderers.
- **FU-2.** Audit all 100+ existing `SecretStrInput` sites in the codebase. Verify none depend on plaintext round-trip. Document decisions.
- **FU-3.** Starter project regen after this lands: run `scripts/ci/update_starter_projects.py` to refresh all starters with the new `auto_promote` flag in their serialized form.
- **FU-4.** Consider promoting `SecretStrInput.auto_promote=True` documentation to the developer-facing "custom component authoring" guide once we're confident the cross-cutting change is stable.

## 13. Implementation plan

Out of scope for this spec. Plan will be written next via the `superpowers:writing-plans` skill and saved to `docs/superpowers/plans/`.

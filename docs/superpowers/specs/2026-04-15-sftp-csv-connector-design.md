# SFTP CSV Upload Component — Design

**Date:** 2026-04-15
**Branch:** `platform-multi-tenant`
**Status:** Approved for planning

## Summary

A single Langflow component, `SFTP CSV Upload`, that takes tabular data from an upstream node, serializes it to CSV with configurable settings, and uploads it to an SFTP destination. Modeled loosely on the ADP connector pattern (`src/lfx/src/lfx/components/adp/`) but collapsed into one component because SFTP doesn't need the multi-consumer auth split that ADP does.

## Goals

- Drag-and-drop SFTP export inside a flow.
- Support both password and SSH-key authentication.
- Expose the CSV options that matter for real-world downstream parsers (delimiter, header, encoding, quote char, quoting policy, line terminator, null representation).
- Safe-by-default but easy first connection (optional host-key fingerprint).

## Non-goals

- Scheduled / org-wide background exports (no cron, no platform feature).
- SFTP downloads, directory listing, deletes, or any other SFTP operation.
- Auto-creation of remote directories.
- Retry logic.
- Streaming uploads for very large datasets (deferred until needed).
- Per-org credential storage in a connector table — credentials live on the component instance in the flow.

## Architecture

```
src/lfx/src/lfx/components/sftp/
├── __init__.py                 # re-exports SFTPCSVUploadComponent
└── sftp_csv_upload.py          # the component
```

- New runtime dependency: `asyncssh` (added to `src/lfx/pyproject.toml`).
- Component class extends `lfx.custom.custom_component.component.Component`.
- Multi-tenant: the component is a flow node and inherits the org context of the flow that runs it. No `organization_id` plumbing in the component.

## Component Inputs

### Connection

| Field | Type | Notes |
|---|---|---|
| `host` | str (required) | |
| `port` | int (default `22`) | |
| `username` | str (required) | |
| `auth_method` | dropdown: `Password` / `SSH Key` (default `Password`) | Toggles fields below |
| `password` | SecretStrInput | Shown when `auth_method=Password` |
| `private_key` | SecretStrInput, multiline | Shown when `auth_method=SSH Key`. PEM contents pasted in |
| `private_key_passphrase` | SecretStrInput, optional | Shown when `auth_method=SSH Key` |
| `host_key_fingerprint` | str, optional, advanced | SHA-256 fingerprint. Empty = auto-accept |

### Data

| Field | Type | Notes |
|---|---|---|
| `data` | DataInput | Accepts `DataFrame`, single `Data`, or list of `Data` / list of dicts |

### Destination

| Field | Type | Notes |
|---|---|---|
| `remote_directory` | str (required) | e.g. `/exports`. Must exist on server |
| `filename` | str (required) | Supports `{timestamp}` → `YYYYMMDD_HHMMSS` UTC, `{date}` → `YYYYMMDD` UTC |

### CSV options (advanced section)

| Field | Type | Default |
|---|---|---|
| `delimiter` | dropdown: `,` `;` `\t` `\|` | `,` |
| `include_header` | bool | `true` |
| `encoding` | dropdown: `utf-8` / `utf-8-sig` / `latin-1` | `utf-8` |
| `quote_char` | str | `"` |
| `quoting` | dropdown: `Minimal` / `All` / `Non-numeric` / `None` | `Minimal` |
| `line_terminator` | dropdown: `\n` / `\r\n` | `\n` |
| `null_representation` | str | empty string |

## Component Output

Single `Message` output:

```
Uploaded <filename> (<rows> rows, <bytes> bytes) to sftp://<host>:<port><remote_path>
```

Errors raise exceptions; Langflow's component runtime surfaces them as the flow error.

## Data Flow

A single async `build_*` method:

1. **Normalize input.**
   - `DataFrame` → use directly.
   - Single `Data` (dict) → wrap in 1-row DataFrame.
   - List of `Data` / list of dicts → `pd.DataFrame.from_records(...)`.
   - Anything else → `TypeError` naming the received type.

2. **Resolve filename.** Substitute `{timestamp}` / `{date}` (UTC, `time.gmtime()`-based — no timezone deps). Join with `remote_directory` via `posixpath.join`. Reject resolved filename containing `/`.

3. **Generate CSV bytes in memory.** Map `quoting` dropdown to `csv.QUOTE_*` constants. Call:
   ```python
   df.to_csv(buf, index=False, sep=..., header=...,
             quotechar=..., quoting=..., lineterminator=...,
             na_rep=..., encoding=...)
   ```
   into a `BytesIO`. Capture `len(buf)` for the result message.

4. **Open SFTP connection.**
   ```python
   async with asyncssh.connect(host, port=port, username=username,
                               connect_timeout=30, **auth_kwargs,
                               known_hosts=known_hosts) as conn:
       async with conn.start_sftp_client() as sftp:
           await sftp.put_data(csv_bytes, remote_path)
   ```
   - **Password auth:** `auth_kwargs = {"password": password}`.
   - **SSH key auth:** `auth_kwargs = {"client_keys": [asyncssh.import_private_key(pem, passphrase)]}`.
   - **Host key:** if `host_key_fingerprint` set, use a `known_hosts` callback that computes SHA-256 of the offered key and compares (case-insensitive, normalized format). Else `known_hosts=None`.

5. **Return** the result `Message`.

Connection is opened, used, and closed within the single `build_*` call — no pooling, no reuse.

## Error Handling

All errors raise standard exceptions; no silent fallbacks; no retries.

| Case | Exception | Notes |
|---|---|---|
| Missing required field | `ValueError` (names the field) | Validated before any network call |
| Filename contains `/` after substitution | `ValueError` | "use remote_directory" |
| Unsupported `data` type | `TypeError` | Names received type |
| Empty DataFrame | (no error) | Uploads header-only or zero-byte file |
| Invalid private key / wrong passphrase | `asyncssh.KeyImportError` / `KeyEncryptionError` | Re-raised as-is |
| Auth failure | `asyncssh.PermissionDenied` | Re-raised as-is |
| Host key fingerprint mismatch | `ValueError` | "expected X, got Y" |
| Connection failure (DNS / refused / timeout) | `asyncssh.Error` / `OSError` | 30s connect timeout |
| Remote directory missing | `asyncssh.SFTPNoSuchFile` | We do **not** auto-create dirs |
| Remote write permission denied | `asyncssh.SFTPPermissionDenied` | Re-raised as-is |

Rationale for no retries: SFTP failures are almost always configuration problems, not transient. Retries mask root cause. Flow authors can add retry logic at the flow level.

## Testing

### Unit tests — `src/lfx/tests/components/sftp/test_sftp_csv_upload.py`

Fast, no network. Mock `asyncssh.connect`.

- **Input normalization:** DataFrame, single Data, list-of-dicts, unsupported type.
- **Filename templating:** `{timestamp}`, `{date}`, literal pass-through, rejected `/` in resolved filename.
- **CSV generation:** parametrized round-trip across all 7 CSV options (delimiter, header on/off, each encoding, each quoting policy, both line terminators, null representation).
- **Validation:** missing required fields raise `ValueError` and `asyncssh.connect` is never called.
- **Auth dispatch:** password mode passes `password=` to connect; key mode passes `client_keys=`.
- **Host key:** fingerprint mismatch raises `ValueError`; match passes; empty sets `known_hosts=None`.

### Integration test — `test_sftp_csv_upload_integration.py` (marked `@pytest.mark.integration`)

Opt-in. Uses asyncssh's in-process SFTP server APIs (no Docker, no extra deps).

- Happy path: connect → upload → assert file exists on server with expected bytes → assert returned Message has correct row count and byte size.
- Failure path: bad credentials → `PermissionDenied` propagates.

## Open Questions

None at design time. All settled in the brainstorming session.

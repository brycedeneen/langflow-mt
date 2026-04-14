# ADP Connector Bundle — Design Spec

**Date:** 2026-04-14
**Branch:** `feat/adp-connector`
**Status:** Approved for planning

## Goal

Ship a Langflow bundle that lets users connect to ADP's APIs and ADP's MCP server from a flow, with a single auth component feeding both a typed API Request component and an MCP toolbox component.

## Scope (v1)

Three components:

1. **ADP Auth** — encapsulates OAuth 2.0 client_credentials over mTLS; outputs a structured `ADPConnection` object.
2. **ADP API Request** — consumes `ADPConnection`; makes authenticated, mTLS-backed requests to `https://api.adp.com` with a curated endpoint dropdown, simple pagination toggle, and `$top`/`$skip` handling.
3. **ADP MCP** — consumes `ADPConnection`; connects to ADP's MCP server over Streamable HTTP as a toolbox (tools plug into Agent components).

Out of scope for v1: typed per-endpoint components, streaming responses, write-path helpers beyond raw HTTP methods, UI tests, token caching across process restarts.

## Architecture

### Layout

```
src/lfx/src/lfx/components/adp/
├── __init__.py
├── adp_auth.py           # ADPAuthComponent — produces ADPConnection
├── adp_api_request.py    # ADPAPIRequestComponent — consumes ADPConnection
├── adp_mcp.py            # ADPMCPComponent — consumes ADPConnection (toolbox)
└── _shared.py            # ADPConnection, token fetch, mTLS httpx client builder
```

Follows existing vendor-bundle convention (e.g., `notion/`, `composio/`) with `__init__.py` re-exports.

### Shared schema — `ADPConnection`

Structured object passed between components. Shape:

```
access_token: str
token_expires_at: datetime (UTC)
client_id: str
client_secret: SecretStr
cert_source: "path" | "pem"
cert_path: str | None
key_path: str | None
cert_pem: SecretStr | None
key_pem: SecretStr | None
api_base_url: str = "https://api.adp.com"
mcp_base_url: str = "https://mcp.adp.com/..."   # placeholder — confirm real URL before GA
```

### Shared helpers — `_shared.py`

- `build_mtls_httpx_client(conn) -> httpx.AsyncClient` — constructs an httpx client with cert/key wired in (from path or PEM); reused by all three components.
- `fetch_token(conn, *, force: bool = False) -> None` — performs client_credentials + mTLS + `application/x-www-form-urlencoded` POST to the token URL; updates `conn.access_token` and `conn.token_expires_at`. Respects 55-min cache unless `force=True`.

All auth/mTLS complexity lives in `_shared.py` so components stay thin.

### Data flow

```
[ADP Auth] --connection--> [ADP API Request] --data--> [downstream]
              \
               --connection--> [ADP MCP] --tools--> [Agent]
```

Auth runs once; its output fans out to any number of consumers. Each consumer builds its own mTLS httpx client from the connection — no shared client state across components.

## Component: ADP Auth

**display_name:** `"ADP Auth"` · **icon:** `"Key"` · **name:** `"ADPAuth"`

### Inputs

| Name | Type | Required | Notes |
|---|---|---|---|
| `client_id` | `SecretStrInput` | yes | |
| `client_secret` | `SecretStrInput` | yes | |
| `cert_source` | `TabInput` | yes | Options `["File Path", "PEM"]`, default `"File Path"`, `real_time_refresh=True` |
| `cert_path` | `MessageTextInput` | when `cert_source=="File Path"` | Absolute path to PEM cert |
| `key_path` | `MessageTextInput` | when `cert_source=="File Path"` | Absolute path to PEM key |
| `cert_pem` | `SecretStrInput` (multiline) | when `cert_source=="PEM"` | Pasted cert contents |
| `key_pem` | `SecretStrInput` (multiline) | when `cert_source=="PEM"` | Pasted key contents |
| `token_url` | `MessageTextInput` | advanced | Default `https://accounts.adp.com/auth/oauth/v2/token` — overridable for staging |

### Output

- `connection` → `ADPConnection`

### Behavior

1. Validate required fields; fail early with actionable messages (field name, file-not-found, etc.).
2. If cached `access_token` is present and `now < token_expires_at`, reuse it.
3. Otherwise, POST to `token_url` with body `grant_type=client_credentials&client_id=…&client_secret=…` as `application/x-www-form-urlencoded`, using an mTLS httpx client built from the configured cert/key.
4. On success, set `access_token`; set `token_expires_at = now + 55 min` (our explicit contract — we ignore ADP's `expires_in` even if returned).
5. Return populated `ADPConnection`.

### Caching

In-memory on the component instance. Survives across runs of the same component instance within a process; cold on restart (acceptable). No global cache.

### Error behavior

- Network / TLS failures → raise with response body when available (helps diagnose bad certs).
- 4xx from token endpoint → surface ADP's OAuth error payload verbatim.
- 5xx / timeouts → raise; no automatic retry (user re-runs).

## Component: ADP API Request

**display_name:** `"ADP API Request"` · **icon:** `"Globe"` · **name:** `"ADPAPIRequest"`

### Inputs

| Name | Type | Required | Notes |
|---|---|---|---|
| `connection` | `HandleInput` (`ADPConnection`) | yes | |
| `endpoint` | `DropdownInput` | yes | `real_time_refresh=True` — see endpoint list below |
| `custom_path` | `MessageTextInput` | when `endpoint=="Other (custom path)"` | Leading-slash path, e.g. `/hr/v2/workers` |
| `resource_id` | `MessageTextInput` | no | When set, substituted into `{aoid}` placeholder or appended for by-ID lookup |
| `method` | `DropdownInput` | yes, advanced | `["GET", "POST", "PATCH", "PUT", "DELETE"]`, default `"GET"` |
| `query_params` | `DataInput` | advanced | Extra OData filters (e.g., `$filter`, `$select`) |
| `body` | `TableInput` | advanced, non-GET only | |
| `result_mode` | `TabInput` | yes | `["Top 20", "All"]`, default `"Top 20"` |
| `timeout` | `IntInput` | advanced | Seconds; default `30` |

### Endpoint dropdown (v1)

| Label | Path |
|---|---|
| Workers | `/hr/v2/workers` (with optional `/{aoid}`) |
| Worker Demographics | `/hr/v2/worker-demographics` |
| Pay Statements | `/payroll/v1/workers/{aoid}/pay-statements` |
| Time Cards | `/time/v2/workers/{aoid}/time-cards` |
| Jobs | `/hr/v1/jobs` |
| Meta | `/core/v1/meta` *(placeholder — confirm)* |
| Other (custom path) | User-entered |

List-vs-by-ID is a single entry per resource: empty `resource_id` → list endpoint; filled → substituted into `{aoid}` or appended.

### Output

- `data` → `Data` (single object for by-ID; flat list concatenated across pages for list endpoints when `result_mode=="All"`)

### Behavior

1. Resolve path: dropdown label → template; or take `custom_path`. Substitute `{aoid}` with `resource_id` when present.
2. Build full URL: `connection.api_base_url + path`.
3. Build mTLS httpx client from connection; set `Authorization: Bearer {connection.access_token}`.
4. Execute:
   - `result_mode=="Top 20"`: single request with `$top=20` merged into query params.
   - `result_mode=="All"`: loop with `$top=100` and incrementing `$skip`, concatenate results, stop when response returns fewer rows than `$top` or no items. Safety cap: 1000 iterations.
5. **401 handling:** call `fetch_token(conn, force=True)` once, retry request, then fail if still 401.
6. Return `Data`.

### SSRF

Base URL is static and user only provides a path, so SSRF surface is minimal. Defense in depth: run the composed final URL through `validate_url_for_ssrf` before request.

## Component: ADP MCP

**display_name:** `"ADP MCP"` · **icon:** `"Plug"` · **name:** `"ADPMCP"`

Toolbox pattern — mirrors `src/lfx/src/lfx/components/models_and_agents/mcp_component.py`. Connects to ADP's MCP server over Streamable HTTP, lists its tools, exposes them as Langflow tool objects suitable for Agent components.

### Inputs

| Name | Type | Required | Notes |
|---|---|---|---|
| `connection` | `HandleInput` (`ADPConnection`) | yes | |
| `mcp_url` | `MessageTextInput` | advanced | Defaults to `connection.mcp_base_url` |
| `tool_filter` | `MessageTextInput` / multi-select | advanced | Restrict which tools are exposed |

### Output

- `tools` → list of Langflow-compatible tool objects (drop-in with Agent).

### Behavior

- Build Streamable HTTP MCP transport with:
  - `Authorization: Bearer {connection.access_token}` header
  - Underlying httpx client built via `build_mtls_httpx_client(connection)`
- List tools; optionally filter; expose as Langflow tools.
- **401 handling:** on auth errors during tool-list or tool-call, `fetch_token(conn, force=True)`, rebuild transport, retry once.

### Implementation risk

The existing `mcp_component.py` may not currently accept a custom httpx client for mTLS. If so, the implementation plan should extend its transport-builder to accept an injected client factory, rather than duplicating MCP plumbing. Verify during planning; may expand scope.

## Error handling (cross-component summary)

| Failure | Behavior |
|---|---|
| Missing cert/key/credentials | Auth fails early with specific field name |
| Invalid cert/key format | Auth fails with TLS error + hint |
| Token endpoint 4xx | Surface ADP OAuth error payload verbatim |
| Token endpoint 5xx / network | Raise with response body; no automatic retry |
| 401 from API Request / MCP | Force-refresh token once, retry; fail if still 401 |
| 4xx from ADP API | Return error `Data` with status + body |
| 5xx from ADP API | Raise; no automatic retry |
| Pagination loop stuck | Safety cap at 1000 pages |

## Testing

Unit tests in `src/lfx/tests/unit/components/adp/`:

- **Auth:** token fetch with mocked httpx; cache hit/miss; 55-min expiry boundary; `force=True` refresh; cert source toggle (path vs PEM); missing-field validation; 4xx surfacing.
- **API Request:** path resolution (dropdown/custom/ID substitution); `Top 20` vs `All` pagination (including early-stop and 1000-cap); 401 retry path; SSRF validation; method gating for body.
- **MCP:** transport construction with auth headers + mTLS; 401 retry; tool listing and `tool_filter`.

Integration tests optional, gated behind env vars with real ADP sandbox credentials — skip if unset. Pattern already used in repo for vendor integrations.

Reuse httpx mocking patterns from existing `api_request.py` tests.

No UI / e2e tests in v1.

## Open questions / placeholders

- **MCP base URL** — real value pending; `https://mcp.adp.com/...` used as placeholder.
- **Meta endpoint path** — `/core/v1/meta` is a placeholder; confirm when the full endpoint list is provided.
- **Extended endpoint list** — user will provide full list after scaffold lands; dropdown is designed to grow.

## Follow-ups (post-v1)

- Typed per-endpoint components (e.g., "ADP Workers") with strongly typed response models.
- Cross-process / shared token cache if latency from repeated component instantiation becomes a problem.
- Streaming responses for very large pay / time datasets.
- Sample flow + integration-test fixture against ADP sandbox.

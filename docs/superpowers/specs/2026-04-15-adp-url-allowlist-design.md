# ADP URL Host Allowlist — Design

**Date:** 2026-04-15
**Branch:** `feat/adp-connector`
**Related:** `docs/superpowers/specs/2026-04-14-adp-connector-design.md`

## Problem

Two inputs on the new ADP connector bundle let a flow author redirect live ADP
credentials or tokens to an attacker-controlled host:

1. `ADPAuthComponent.token_url` (`adp_auth.py`) — user-editable `MessageTextInput`
   whose value flows into `_post_token_request`, which POSTs `client_id` and
   `client_secret` as form data to that URL over the tenant's mTLS client.
2. `ADPMCPComponent.mcp_url` (`adp_mcp.py`) — user-editable `MessageTextInput`
   that fully replaces `conn.mcp_base_url` (scheme + host + path). The live
   OAuth access token is sent as `Authorization: Bearer …` to that URL.

Neither input has scheme enforcement, host allowlist, or SSRF validation. In
Langflow's multi-tenant / shared-flow threat model a malicious flow can
exfiltrate ADP client credentials and live bearer tokens to an arbitrary host.

## Fix

Enforce an explicit ADP-only host allowlist and `https` scheme on every URL
used by the ADP bundle. Scope is limited to
`src/lfx/src/lfx/components/adp/` — no changes to the generic SSRF helper or
other components.

### New helper in `_shared.py`

```python
ALLOWED_ADP_HOST_SUFFIX = ".adp.com"

def _validate_adp_url(url: str, *, field_name: str) -> str:
    """Require https + host is exactly 'adp.com' or ends in '.adp.com'.

    Rejects off-allowlist hosts, non-https schemes, URLs with userinfo
    (`user@host`), missing/empty hosts, and malformed URLs. Returns the
    URL unchanged on success. Raises ValueError with field_name in the
    message on reject.
    """
```

Implementation uses `urllib.parse.urlsplit`. Rejection conditions:

- `scheme != "https"`
- `hostname` missing or empty
- `"@"` present in `netloc` (userinfo component)
- hostname (lowercased, port stripped by `urlsplit.hostname`) is neither
  exactly `adp.com` nor suffixed with `.adp.com`

The suffix check is an explicit `hostname == "adp.com" or hostname.endswith(".adp.com")`,
not a wildcard regex, so `evil-adp.com` and `adp.com.attacker.tld` are both
rejected.

### Call sites

1. **`adp_auth.py` `build_connection()`** — validate `token_url` before
   constructing `ADPConnection`. Fails fast at configure time, before any
   credential is sent.
2. **`adp_mcp.py` `build_tools()`** — validate the effective URL (user-supplied
   `mcp_url` if non-empty, else `conn.mcp_base_url`) before the
   `_connect_to_server(url, headers=…)` call. The bearer token must not be
   constructed into headers until after validation passes.
3. **`adp_api_request.py`** — validate the fully constructed request URL. Drop
   the existing `validate_url_for_ssrf(..., warn_only=True)` call (the
   allowlist is strictly stronger). Host there isn't user-controlled today; this
   keeps the fix uniform across the bundle.

### Error handling

`_validate_adp_url` raises `ValueError`. Component builders let it propagate —
this matches the existing pattern in `build_mtls_httpx_client` (e.g. the
`cert_path and key_path are required …` path). No special wrapping.

### Tests (new, in `src/lfx/tests/unit/components/adp/`)

Unit tests for `_validate_adp_url`:

- Accepts: `https://api.adp.com`, `https://accounts.adp.com/auth/oauth/v2/token`,
  `https://mcp.adp.com/mcp`, `https://adp.com` (bare apex), host with port
  (`https://api.adp.com:8443/x`).
- Rejects: `http://api.adp.com` (scheme), `https://evil.com`,
  `https://evil-adp.com` (suffix spoof), `https://adp.com.attacker.tld`
  (suffix spoof), `https://api.adp.com@attacker.tld` (userinfo spoof),
  `""`, `"not a url"`, `"https:///"` (missing host).

Component-level tests:

- `ADPAuthComponent.build_connection` raises `ValueError` when `token_url` is
  off-allowlist; does not construct an `ADPConnection`.
- `ADPMCPComponent.build_tools` raises `ValueError` when `mcp_url` is
  off-allowlist and `MCPStreamableHttpClient._connect_to_server` is **not**
  called (verified via mock). This is the critical invariant: the bearer token
  must never leave the process on an off-allowlist URL.
- `ADPAPIRequestComponent`: existing tests continue to pass against the
  default `api.adp.com` host; one added test confirms a mutated
  `conn.api_base_url` pointing off-allowlist is rejected.

## Non-goals

- Configurable allowlist via env var (explicitly rejected in brainstorming in
  favor of the strict default; revisit only if a real regional/partner host
  outside `*.adp.com` emerges).
- Changes to the generic Langflow `validate_url_for_ssrf` helper.
- Changes to other components' URL handling.

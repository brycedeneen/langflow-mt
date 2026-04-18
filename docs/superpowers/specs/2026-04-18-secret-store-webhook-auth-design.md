# Pluggable Secret Store + Per-Flow Webhook API Keys

**Date**: 2026-04-18
**Status**: Draft

## Problem

In a multi-tenant environment, webhook endpoints cannot be unauthenticated. Callers need a per-flow credential to invoke webhooks, and the platform needs a secure, centralized place to store secrets — not just webhook API keys, but any sensitive configuration (third-party API keys, client secrets, etc.) that flows and platform services will need over time.

## Goals

1. Introduce a pluggable `SecretStore` abstraction for secure secret storage.
2. Implement a HashiCorp Vault backend as the initial provider.
3. Generate and enforce per-flow API keys for all webhook invocations.
4. Ensure tenant isolation — secrets are scoped by organization.

## Non-Goals

- UI for managing secrets beyond the webhook component's key display.
- Key rotation, expiry, or multi-key-per-flow support (future work).
- Migrating existing secrets (e.g., user API keys in the DB) into the new store.

---

## 1. Secret Store Abstraction

### Interface

```python
# src/lfx/src/lfx/services/secret_store/base.py

from abc import ABC, abstractmethod

class SecretStore(ABC):
    """Abstract interface for secure key-value secret storage."""

    @abstractmethod
    async def get(self, path: str) -> dict | None:
        """Retrieve a secret by path. Returns None if not found."""

    @abstractmethod
    async def put(self, path: str, data: dict) -> None:
        """Store or overwrite a secret at the given path."""

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete a secret at the given path. No-op if not found."""

    @abstractmethod
    async def list(self, prefix: str) -> list[str]:
        """List secret keys under a prefix."""
```

### Path Convention

All secret paths are tenant-scoped:

```
{org_id}/{category}/{resource_id}
```

For webhook API keys:

```
{org_id}/webhooks/{flow_id}
```

This ensures strict tenant isolation — one organization's secrets are never accessible via another's path prefix.

### Factory

```python
# src/lfx/src/lfx/services/secret_store/factory.py

def get_secret_store() -> SecretStore:
    """Return the configured SecretStore implementation based on SECRET_STORE_BACKEND env var."""
```

The factory reads `SECRET_STORE_BACKEND` (default: `vault`) and returns the appropriate implementation. This is the single point where backend selection happens — consumers never import a concrete implementation directly.

---

## 2. Vault Implementation

### Library

Uses the `hvac` Python library (HashiCorp Vault client). Since `hvac` is synchronous, the `VaultSecretStore` wraps calls with `asyncio.to_thread` to avoid blocking the event loop.

### Configuration (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_STORE_BACKEND` | `vault` | Which backend to use |
| `VAULT_ADDR` | `http://localhost:8200` | Vault server URL |
| `VAULT_TOKEN` | (required) | Auth token for Vault |
| `VAULT_MOUNT_POINT` | `secret` | KV v2 mount point |

### Implementation Details

- Uses Vault's KV v2 secrets engine (the default in dev mode).
- All operations go through the `hvac.Client` KV v2 methods (`read_secret_version`, `create_or_update_secret`, `delete_metadata_and_all_versions`, `list_secrets`).
- The Vault client is initialized once and reused (connection pooling via `requests.Session` under the hood).
- Errors from Vault (connection failures, permission denied, etc.) propagate as exceptions — callers handle retry/fallback as appropriate.

### File Layout

```
src/lfx/src/lfx/services/secret_store/
  __init__.py        # Exports SecretStore, get_secret_store
  base.py            # SecretStore ABC
  vault.py           # VaultSecretStore implementation
  factory.py         # get_secret_store() factory function
```

---

## 3. Per-Flow Webhook API Keys

### Key Format

```
ADP-APICPRO-{48 URL-safe base64 characters}
```

- The `ADP-APICPRO-` prefix identifies the key type at a glance.
- The 48-character suffix is generated via `secrets.token_urlsafe(36)` which produces 48 characters of URL-safe base64, giving ~256 bits of entropy.
- Total key length: 60 characters.

### Key Lifecycle

**Generation**: When a flow containing a webhook component is created or updated (and no key exists yet for that flow), auto-generate an API key and store it in Vault at:

```
{org_id}/webhooks/{flow_id}
```

Payload stored:
```json
{
  "api_key": "ADP-APICPRO-...",
  "created_at": "2026-04-18T12:00:00Z"
}
```

**Retrieval**: The webhook component loads the key from Vault on component build to display it in the UI.

**Deletion**: When a flow is deleted, its webhook API key is deleted from Vault.

**No rotation yet**: Key rotation and expiry are out of scope for this iteration.

### Key Display

The `WebhookComponent` gets a new read-only field (`api_key`) that displays the generated key. The existing `curl` field template is updated to include the `-H "x-api-key: {key}"` header in the example command.

---

## 4. Webhook Endpoint Changes

The `POST /webhook/{flow_id_or_name}` endpoint enforces API key auth for all requests:

1. Extract `x-api-key` from the request **header only** (not query params — avoid key leakage in logs/URLs).
2. Resolve the flow and its organization.
3. Fetch the stored API key from the secret store at `{org_id}/webhooks/{flow_id}`.
4. **Constant-time compare** (`hmac.compare_digest`) the provided key against the stored key.
5. If missing: return `401 Unauthorized`.
6. If invalid: return `403 Forbidden`.
7. If valid: proceed with execution as the flow owner.

This applies to both the in-process and distributed execution paths in the endpoint.

The existing `WEBHOOK_AUTH_ENABLE` toggle and user-API-key-based auth become secondary to this per-flow key check. The per-flow key is always required; the existing user-level auth is no longer needed for webhook callers.

---

## 5. Component Changes

### WebhookComponent Updates

```python
inputs = [
    # ... existing data, curl, endpoint fields ...
    MultilineInput(
        name="api_key",
        display_name="API Key",
        info="Auto-generated API key required for webhook authentication. Include as x-api-key header.",
        advanced=False,
        copy_field=True,
        input_types=[],
        # Value populated dynamically from secret store
    ),
]
```

The `curl` field value is updated to include the auth header:

```
curl -X POST {endpoint} -H "x-api-key: {api_key}" -H "Content-Type: application/json" -d '{"key": "value"}'
```

---

## 6. Error Handling

| Scenario | Behavior |
|----------|----------|
| Vault unreachable on webhook call | Return 503 Service Unavailable |
| Vault unreachable on flow save | Log warning, skip key generation (retry on next save) |
| Flow has no stored API key | Return 401 (key not yet provisioned) |
| Secret store backend misconfigured | Fail fast on startup with clear error message |

---

## 7. Testing Strategy

- **Unit tests**: Mock the `SecretStore` interface to test key generation logic, endpoint auth validation, and component behavior independently of Vault.
- **Integration tests**: Test `VaultSecretStore` against the dev Vault Docker container to verify real read/write/delete/list operations.
- **Endpoint tests**: Verify 401/403/200 behavior for missing, invalid, and valid API keys on the webhook endpoint.

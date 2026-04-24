# Pluggable Secret Store + Per-Flow Webhook API Keys — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** ✅ Tasks 1–11 shipped (see reconciliation note below). Full unit + integration suites green on 2026-04-24: `src/lfx/tests/unit/services/test_secret_store.py` (21 passed), `src/backend/base/langflow/tests/services/database/models/flow/test_webhook_auth.py` (14 passed), `src/lfx/tests/integration/services/test_vault_secret_store.py` (8 passed against local Vault dev). Task 12 (full suite run) complete for the secret-store / webhook-auth surface. Plan checkboxes below were never flipped during implementation — relying on commit history + code inspection for ground truth. Bonus scope added beyond plan: `POST /flows/{flow_id}/webhook-api-key` reset endpoint (`flows.py:848`) + `webhookFieldComponent` UI. Gaps tracked as follow-ups: no direct HTTP-route test for the reset endpoint, no cross-org regression, no Jest coverage on the UI component.

**Commits (chronological):** `dbcaf22288` (ABC) · `d2ceb2c676` (settings) · `bc82a30b33` (VaultSecretStore) · `8f9d716dc3` (factory) · `561140e185` (factory singleton fix) · `189fcd2da5` (hvac v3 compat) · `1cf2dbcb9c` (key-gen helper) · `cd5ba836ec` (enforce on webhook endpoint) · `9466867b22` (WebhookComponent UI field).

**Goal:** Add a pluggable secret store abstraction (Vault-backed) and enforce per-flow API key authentication on all webhook invocations in a multi-tenant environment.

**Architecture:** A `SecretStore` ABC lives in the lfx services layer with a Vault KV v2 implementation using `hvac`. Per-flow webhook API keys (`ADP-APICPRO-{48 chars}`) are generated on flow create/update when a webhook component is present, stored in Vault at `{org_id}/webhooks/{flow_id}`, and validated via constant-time compare on every webhook request.

**Tech Stack:** Python 3.12, `hvac` (HashiCorp Vault client), `pydantic-settings`, `pytest`, `pytest-asyncio`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `src/lfx/src/lfx/services/secret_store/__init__.py` | Exports `SecretStore`, `get_secret_store` |
| `src/lfx/src/lfx/services/secret_store/base.py` | `SecretStore` ABC with `get`, `put`, `delete`, `list` |
| `src/lfx/src/lfx/services/secret_store/vault.py` | `VaultSecretStore` — `hvac`-backed implementation |
| `src/lfx/src/lfx/services/secret_store/factory.py` | `get_secret_store()` factory keyed off settings |
| `src/lfx/src/lfx/services/secret_store/settings.py` | `SecretStoreSettings` pydantic-settings model |
| `src/lfx/tests/unit/services/test_secret_store.py` | Unit tests for SecretStore (mocked Vault) |
| `src/lfx/tests/integration/services/test_vault_secret_store.py` | Integration tests against real Vault |
| `src/lfx/tests/unit/services/test_webhook_auth.py` | Unit tests for webhook API key generation and validation |

### Modified Files

| File | Change |
|------|--------|
| `src/lfx/pyproject.toml` | Add `hvac` dependency |
| `src/lfx/src/lfx/services/settings/base.py` | Add `SecretStoreSettings` to `Settings` |
| `src/lfx/src/lfx/components/input_output/webhook.py` | Add `api_key` display field, update `curl` template |
| `src/backend/base/langflow/api/v1/endpoints.py` | Add per-flow API key validation before webhook execution |
| `src/backend/base/langflow/api/v1/flows.py` | Generate/store API key on flow create/update when webhook present |
| `src/backend/base/langflow/services/database/models/flow/utils.py` | Add helper to generate webhook API keys |

---

## Task 1: Add `hvac` Dependency

**Files:**
- Modify: `src/lfx/pyproject.toml`

- [x] **Step 1: Add hvac to pyproject.toml dependencies**

In `src/lfx/pyproject.toml`, add `hvac` to the `dependencies` list:

```toml
"hvac>=2.0.0,<3.0.0",
```

Add it after the existing `cryptography` entry.

- [x] **Step 2: Install the updated dependencies**

Run: `cd src/lfx && uv sync`
Expected: clean install with hvac resolved

- [x] **Step 3: Verify hvac is importable**

Run: `cd src/lfx && uv run python -c "import hvac; print(hvac.__version__)"`
Expected: prints a version like `2.x.x`

- [x] **Step 4: Commit**

```bash
git add src/lfx/pyproject.toml src/lfx/uv.lock
git commit -m "build: add hvac dependency for Vault secret store"
```

---

## Task 2: SecretStore ABC

**Files:**
- Create: `src/lfx/src/lfx/services/secret_store/__init__.py`
- Create: `src/lfx/src/lfx/services/secret_store/base.py`
- Test: `src/lfx/tests/unit/services/test_secret_store.py`

- [x] **Step 1: Write the failing test for SecretStore interface**

Create `src/lfx/tests/unit/services/test_secret_store.py`:

```python
"""Tests for SecretStore ABC."""

import pytest

from lfx.services.secret_store.base import SecretStore


class ConcreteSecretStore(SecretStore):
    """Minimal concrete implementation for testing the ABC."""

    def __init__(self):
        self._store: dict[str, dict] = {}

    async def get(self, path: str) -> dict | None:
        return self._store.get(path)

    async def put(self, path: str, data: dict) -> None:
        self._store[path] = data

    async def delete(self, path: str) -> None:
        self._store.pop(path, None)

    async def list(self, prefix: str) -> list[str]:
        return [k for k in self._store if k.startswith(prefix)]


class TestSecretStoreABC:
    @pytest.mark.asyncio
    async def test_put_and_get(self):
        store = ConcreteSecretStore()
        await store.put("org1/webhooks/flow1", {"api_key": "test123"})
        result = await store.get("org1/webhooks/flow1")
        assert result == {"api_key": "test123"}

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self):
        store = ConcreteSecretStore()
        result = await store.get("nonexistent/path")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self):
        store = ConcreteSecretStore()
        await store.put("org1/webhooks/flow1", {"api_key": "test123"})
        await store.delete("org1/webhooks/flow1")
        result = await store.get("org1/webhooks/flow1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_is_noop(self):
        store = ConcreteSecretStore()
        await store.delete("nonexistent/path")  # should not raise

    @pytest.mark.asyncio
    async def test_list_by_prefix(self):
        store = ConcreteSecretStore()
        await store.put("org1/webhooks/flow1", {"key": "a"})
        await store.put("org1/webhooks/flow2", {"key": "b"})
        await store.put("org2/webhooks/flow3", {"key": "c"})
        result = await store.list("org1/webhooks/")
        assert sorted(result) == ["org1/webhooks/flow1", "org1/webhooks/flow2"]

    @pytest.mark.asyncio
    async def test_list_empty_prefix(self):
        store = ConcreteSecretStore()
        result = await store.list("nonexistent/")
        assert result == []

    def test_cannot_instantiate_abc_directly(self):
        with pytest.raises(TypeError):
            SecretStore()  # type: ignore[abstract]
```

- [x] **Step 2: Run the test to verify it fails**

Run: `cd src/lfx && uv run pytest tests/unit/services/test_secret_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lfx.services.secret_store'`

- [x] **Step 3: Write the SecretStore ABC**

Create `src/lfx/src/lfx/services/secret_store/base.py`:

```python
"""Abstract base class for pluggable secret storage."""

from __future__ import annotations

from abc import ABC, abstractmethod


class SecretStore(ABC):
    """Abstract interface for secure key-value secret storage.

    All paths follow the convention: {org_id}/{category}/{resource_id}
    to enforce tenant isolation.
    """

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

Create `src/lfx/src/lfx/services/secret_store/__init__.py`:

```python
"""Pluggable secret store service."""

from lfx.services.secret_store.base import SecretStore

__all__ = ["SecretStore"]
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `cd src/lfx && uv run pytest tests/unit/services/test_secret_store.py -v`
Expected: all 7 tests PASS

- [x] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/services/secret_store/ src/lfx/tests/unit/services/test_secret_store.py
git commit -m "feat: add SecretStore ABC for pluggable secret storage"
```

---

## Task 3: SecretStore Settings

**Files:**
- Create: `src/lfx/src/lfx/services/secret_store/settings.py`
- Modify: `src/lfx/src/lfx/services/settings/base.py`
- Test: `src/lfx/tests/unit/services/test_secret_store.py` (append)

- [x] **Step 1: Write the failing test for SecretStoreSettings**

Append to `src/lfx/tests/unit/services/test_secret_store.py`:

```python
from lfx.services.secret_store.settings import SecretStoreSettings


class TestSecretStoreSettings:
    def test_default_values(self):
        settings = SecretStoreSettings()
        assert settings.SECRET_STORE_BACKEND == "vault"
        assert settings.VAULT_ADDR == "http://localhost:8200"
        assert settings.VAULT_MOUNT_POINT == "secret"

    def test_vault_token_required_string(self):
        settings = SecretStoreSettings(VAULT_TOKEN="myroot")
        assert settings.VAULT_TOKEN.get_secret_value() == "myroot"

    def test_override_backend(self):
        settings = SecretStoreSettings(SECRET_STORE_BACKEND="memory")
        assert settings.SECRET_STORE_BACKEND == "memory"
```

- [x] **Step 2: Run the test to verify it fails**

Run: `cd src/lfx && uv run pytest tests/unit/services/test_secret_store.py::TestSecretStoreSettings -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lfx.services.secret_store.settings'`

- [x] **Step 3: Create the settings model**

Create `src/lfx/src/lfx/services/secret_store/settings.py`:

```python
"""Configuration for the secret store service."""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecretStoreSettings(BaseSettings):
    """Settings for the pluggable secret store."""

    model_config = SettingsConfigDict(env_prefix="LANGFLOW_", extra="ignore")

    SECRET_STORE_BACKEND: str = Field(
        default="vault",
        description="Secret store backend: 'vault', 'memory' (for testing).",
    )
    VAULT_ADDR: str = Field(
        default="http://localhost:8200",
        description="HashiCorp Vault server URL.",
    )
    VAULT_TOKEN: SecretStr = Field(
        default=SecretStr(""),
        description="Authentication token for Vault.",
    )
    VAULT_MOUNT_POINT: str = Field(
        default="secret",
        description="Vault KV v2 mount point.",
    )
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `cd src/lfx && uv run pytest tests/unit/services/test_secret_store.py::TestSecretStoreSettings -v`
Expected: all 3 tests PASS

- [x] **Step 5: Wire settings into the main Settings class**

In `src/lfx/src/lfx/services/settings/base.py`, add an import at the top of the file (with the other imports):

```python
from lfx.services.secret_store.settings import SecretStoreSettings
```

Then add a field to the `Settings` class body (after the existing fields):

```python
secret_store: SecretStoreSettings = Field(default_factory=SecretStoreSettings)
```

- [x] **Step 6: Commit**

```bash
git add src/lfx/src/lfx/services/secret_store/settings.py src/lfx/src/lfx/services/settings/base.py src/lfx/tests/unit/services/test_secret_store.py
git commit -m "feat: add SecretStoreSettings and wire into main Settings"
```

---

## Task 4: VaultSecretStore Implementation

**Files:**
- Create: `src/lfx/src/lfx/services/secret_store/vault.py`
- Test: `src/lfx/tests/unit/services/test_secret_store.py` (append)

- [x] **Step 1: Write the failing test for VaultSecretStore**

Append to `src/lfx/tests/unit/services/test_secret_store.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

from lfx.services.secret_store.vault import VaultSecretStore


class TestVaultSecretStore:
    def _make_store(self) -> VaultSecretStore:
        return VaultSecretStore(
            addr="http://localhost:8200",
            token="myroot",
            mount_point="secret",
        )

    @pytest.mark.asyncio
    async def test_put_calls_vault_create_or_update(self):
        store = self._make_store()
        with patch.object(store._client.secrets.kv.v2, "create_or_update_secret") as mock_write:
            await store.put("org1/webhooks/flow1", {"api_key": "ADP-APICPRO-abc123"})
            mock_write.assert_called_once_with(
                path="org1/webhooks/flow1",
                secret={"api_key": "ADP-APICPRO-abc123"},
                mount_point="secret",
            )

    @pytest.mark.asyncio
    async def test_get_returns_data(self):
        store = self._make_store()
        mock_response = {"data": {"data": {"api_key": "ADP-APICPRO-abc123"}}}
        with patch.object(
            store._client.secrets.kv.v2, "read_secret_version", return_value=mock_response
        ):
            result = await store.get("org1/webhooks/flow1")
            assert result == {"api_key": "ADP-APICPRO-abc123"}

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self):
        store = self._make_store()
        from hvac.exceptions import InvalidPath

        with patch.object(
            store._client.secrets.kv.v2, "read_secret_version", side_effect=InvalidPath()
        ):
            result = await store.get("nonexistent")
            assert result is None

    @pytest.mark.asyncio
    async def test_delete_calls_vault_delete(self):
        store = self._make_store()
        with patch.object(store._client.secrets.kv.v2, "delete_metadata_and_all_versions") as mock_delete:
            await store.delete("org1/webhooks/flow1")
            mock_delete.assert_called_once_with(
                path="org1/webhooks/flow1",
                mount_point="secret",
            )

    @pytest.mark.asyncio
    async def test_delete_nonexistent_is_noop(self):
        store = self._make_store()
        from hvac.exceptions import InvalidPath

        with patch.object(
            store._client.secrets.kv.v2, "delete_metadata_and_all_versions", side_effect=InvalidPath()
        ):
            await store.delete("nonexistent")  # should not raise

    @pytest.mark.asyncio
    async def test_list_returns_keys(self):
        store = self._make_store()
        mock_response = {"data": {"keys": ["flow1", "flow2"]}}
        with patch.object(
            store._client.secrets.kv.v2, "list_secrets", return_value=mock_response
        ):
            result = await store.list("org1/webhooks/")
            assert result == ["flow1", "flow2"]

    @pytest.mark.asyncio
    async def test_list_empty_returns_empty(self):
        store = self._make_store()
        from hvac.exceptions import InvalidPath

        with patch.object(
            store._client.secrets.kv.v2, "list_secrets", side_effect=InvalidPath()
        ):
            result = await store.list("nonexistent/")
            assert result == []
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `cd src/lfx && uv run pytest tests/unit/services/test_secret_store.py::TestVaultSecretStore -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lfx.services.secret_store.vault'`

- [x] **Step 3: Implement VaultSecretStore**

Create `src/lfx/src/lfx/services/secret_store/vault.py`:

```python
"""HashiCorp Vault KV v2 implementation of SecretStore."""

from __future__ import annotations

import asyncio
from functools import partial

import hvac
from hvac.exceptions import InvalidPath

from lfx.services.secret_store.base import SecretStore


class VaultSecretStore(SecretStore):
    """Secret store backed by HashiCorp Vault KV v2 engine.

    Uses hvac (synchronous) with asyncio.to_thread to avoid blocking.
    """

    def __init__(self, addr: str, token: str, mount_point: str = "secret") -> None:
        self._client = hvac.Client(url=addr, token=token)
        self._mount_point = mount_point

    async def get(self, path: str) -> dict | None:
        try:
            response = await asyncio.to_thread(
                self._client.secrets.kv.v2.read_secret_version,
                path=path,
                mount_point=self._mount_point,
            )
            return response["data"]["data"]
        except InvalidPath:
            return None

    async def put(self, path: str, data: dict) -> None:
        await asyncio.to_thread(
            self._client.secrets.kv.v2.create_or_update_secret,
            path=path,
            secret=data,
            mount_point=self._mount_point,
        )

    async def delete(self, path: str) -> None:
        try:
            await asyncio.to_thread(
                self._client.secrets.kv.v2.delete_metadata_and_all_versions,
                path=path,
                mount_point=self._mount_point,
            )
        except InvalidPath:
            pass

    async def list(self, prefix: str) -> list[str]:
        try:
            response = await asyncio.to_thread(
                self._client.secrets.kv.v2.list_secrets,
                path=prefix,
                mount_point=self._mount_point,
            )
            return response["data"]["keys"]
        except InvalidPath:
            return []
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `cd src/lfx && uv run pytest tests/unit/services/test_secret_store.py::TestVaultSecretStore -v`
Expected: all 8 tests PASS

- [x] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/services/secret_store/vault.py src/lfx/tests/unit/services/test_secret_store.py
git commit -m "feat: add VaultSecretStore implementation using hvac KV v2"
```

---

## Task 5: Secret Store Factory

**Files:**
- Create: `src/lfx/src/lfx/services/secret_store/factory.py`
- Modify: `src/lfx/src/lfx/services/secret_store/__init__.py`
- Test: `src/lfx/tests/unit/services/test_secret_store.py` (append)

- [x] **Step 1: Write the failing test for the factory**

Append to `src/lfx/tests/unit/services/test_secret_store.py`:

```python
from lfx.services.secret_store.factory import get_secret_store
from lfx.services.secret_store.settings import SecretStoreSettings


class TestSecretStoreFactory:
    def test_vault_backend(self):
        settings = SecretStoreSettings(
            SECRET_STORE_BACKEND="vault",
            VAULT_ADDR="http://localhost:8200",
            VAULT_TOKEN="myroot",
        )
        store = get_secret_store(settings)
        assert isinstance(store, VaultSecretStore)

    def test_memory_backend(self):
        settings = SecretStoreSettings(SECRET_STORE_BACKEND="memory")
        store = get_secret_store(settings)
        assert isinstance(store, ConcreteSecretStore.__class__) or hasattr(store, "_store")

    def test_unknown_backend_raises(self):
        settings = SecretStoreSettings(SECRET_STORE_BACKEND="unknown_backend")
        with pytest.raises(ValueError, match="Unknown secret store backend"):
            get_secret_store(settings)
```

- [x] **Step 2: Run the test to verify it fails**

Run: `cd src/lfx && uv run pytest tests/unit/services/test_secret_store.py::TestSecretStoreFactory -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lfx.services.secret_store.factory'`

- [x] **Step 3: Implement the factory**

Create `src/lfx/src/lfx/services/secret_store/factory.py`:

```python
"""Factory for creating SecretStore instances based on configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.services.secret_store.base import SecretStore

if TYPE_CHECKING:
    from lfx.services.secret_store.settings import SecretStoreSettings


class InMemorySecretStore(SecretStore):
    """In-memory secret store for testing and development."""

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    async def get(self, path: str) -> dict | None:
        return self._store.get(path)

    async def put(self, path: str, data: dict) -> None:
        self._store[path] = data

    async def delete(self, path: str) -> None:
        self._store.pop(path, None)

    async def list(self, prefix: str) -> list[str]:
        return [k for k in self._store if k.startswith(prefix)]


_instance: SecretStore | None = None


def get_secret_store(settings: SecretStoreSettings | None = None) -> SecretStore:
    """Return a SecretStore instance based on configuration.

    The instance is created on first call and cached for subsequent calls.
    Pass settings explicitly for testing; otherwise reads from the main Settings.
    """
    global _instance  # noqa: PLW0603

    if _instance is not None and settings is None:
        return _instance

    if settings is None:
        from lfx.services.deps import get_settings_service
        settings = get_settings_service().settings.secret_store

    backend = settings.SECRET_STORE_BACKEND

    if backend == "vault":
        from lfx.services.secret_store.vault import VaultSecretStore

        token = settings.VAULT_TOKEN.get_secret_value()
        if not token:
            msg = "VAULT_TOKEN is required when SECRET_STORE_BACKEND=vault"
            raise ValueError(msg)
        store = VaultSecretStore(
            addr=settings.VAULT_ADDR,
            token=token,
            mount_point=settings.VAULT_MOUNT_POINT,
        )
    elif backend == "memory":
        store = InMemorySecretStore()
    else:
        msg = f"Unknown secret store backend: {backend!r}. Supported: 'vault', 'memory'."
        raise ValueError(msg)

    if settings is None:
        _instance = store

    return store
```

- [x] **Step 4: Update the factory test to use correct types**

Replace the `test_memory_backend` test in `TestSecretStoreFactory`:

```python
    def test_memory_backend(self):
        from lfx.services.secret_store.factory import InMemorySecretStore

        settings = SecretStoreSettings(SECRET_STORE_BACKEND="memory")
        store = get_secret_store(settings)
        assert isinstance(store, InMemorySecretStore)
```

- [x] **Step 5: Update `__init__.py` to export factory**

Replace `src/lfx/src/lfx/services/secret_store/__init__.py`:

```python
"""Pluggable secret store service."""

from lfx.services.secret_store.base import SecretStore
from lfx.services.secret_store.factory import get_secret_store

__all__ = ["SecretStore", "get_secret_store"]
```

- [x] **Step 6: Run the tests to verify they pass**

Run: `cd src/lfx && uv run pytest tests/unit/services/test_secret_store.py::TestSecretStoreFactory -v`
Expected: all 3 tests PASS

- [x] **Step 7: Commit**

```bash
git add src/lfx/src/lfx/services/secret_store/ src/lfx/tests/unit/services/test_secret_store.py
git commit -m "feat: add secret store factory with Vault and in-memory backends"
```

---

## Task 6: Webhook API Key Generation Helper

**Files:**
- Modify: `src/backend/base/langflow/services/database/models/flow/utils.py`
- Test: `src/lfx/tests/unit/services/test_webhook_auth.py`

- [x] **Step 1: Write the failing test for key generation**

Create `src/lfx/tests/unit/services/test_webhook_auth.py`:

```python
"""Tests for webhook API key generation and validation."""

import hmac
import re

import pytest


class TestWebhookApiKeyGeneration:
    def test_generate_webhook_api_key_format(self):
        from langflow.services.database.models.flow.utils import generate_webhook_api_key

        key = generate_webhook_api_key()
        assert key.startswith("ADP-APICPRO-")
        suffix = key[len("ADP-APICPRO-"):]
        assert len(suffix) == 48

    def test_generate_webhook_api_key_uniqueness(self):
        from langflow.services.database.models.flow.utils import generate_webhook_api_key

        keys = {generate_webhook_api_key() for _ in range(100)}
        assert len(keys) == 100  # all unique

    def test_generate_webhook_api_key_url_safe(self):
        from langflow.services.database.models.flow.utils import generate_webhook_api_key

        key = generate_webhook_api_key()
        suffix = key[len("ADP-APICPRO-"):]
        # URL-safe base64 uses only alphanumeric, hyphen, and underscore
        assert re.match(r'^[A-Za-z0-9_-]+$', suffix)

    def test_constant_time_compare_valid(self):
        key = "ADP-APICPRO-abc123"
        assert hmac.compare_digest(key, key) is True

    def test_constant_time_compare_invalid(self):
        assert hmac.compare_digest("ADP-APICPRO-abc123", "ADP-APICPRO-wrong") is False
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `cd src/lfx && uv run pytest tests/unit/services/test_webhook_auth.py -v`
Expected: FAIL — `ImportError: cannot import name 'generate_webhook_api_key'`

- [x] **Step 3: Implement the key generation function**

Add to the end of `src/backend/base/langflow/services/database/models/flow/utils.py`:

```python
import secrets


def generate_webhook_api_key() -> str:
    """Generate a per-flow webhook API key.

    Format: ADP-APICPRO-{48 URL-safe base64 characters}
    Provides ~256 bits of entropy.
    """
    return f"ADP-APICPRO-{secrets.token_urlsafe(36)}"
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `cd src/lfx && uv run pytest tests/unit/services/test_webhook_auth.py -v`
Expected: all 5 tests PASS

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/database/models/flow/utils.py src/lfx/tests/unit/services/test_webhook_auth.py
git commit -m "feat: add generate_webhook_api_key() helper"
```

---

## Task 7: Auto-Generate API Key on Flow Create/Update

**Files:**
- Modify: `src/backend/base/langflow/api/v1/flows.py`
- Test: `src/lfx/tests/unit/services/test_webhook_auth.py` (append)

- [x] **Step 1: Write the failing test for key provisioning on flow save**

Append to `src/lfx/tests/unit/services/test_webhook_auth.py`:

```python
from unittest.mock import AsyncMock, patch


class TestWebhookKeyProvisioning:
    @pytest.mark.asyncio
    async def test_provision_webhook_key_stores_in_vault(self):
        """When a flow has a webhook component and no key exists, one is generated and stored."""
        from langflow.services.database.models.flow.utils import generate_webhook_api_key

        mock_store = AsyncMock()
        mock_store.get = AsyncMock(return_value=None)  # no existing key
        mock_store.put = AsyncMock()

        with patch("langflow.api.v1.flows.get_secret_store", return_value=mock_store):
            from langflow.api.v1.flows import _provision_webhook_api_key

            key = await _provision_webhook_api_key(
                org_id="org-123",
                flow_id="flow-456",
                has_webhook=True,
            )

        assert key is not None
        assert key.startswith("ADP-APICPRO-")
        mock_store.put.assert_called_once()
        call_args = mock_store.put.call_args
        assert call_args[0][0] == "org-123/webhooks/flow-456"
        assert "api_key" in call_args[0][1]
        assert "created_at" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_provision_skips_when_key_exists(self):
        """When a key already exists, don't regenerate."""
        mock_store = AsyncMock()
        mock_store.get = AsyncMock(return_value={"api_key": "ADP-APICPRO-existing", "created_at": "2026-01-01"})

        with patch("langflow.api.v1.flows.get_secret_store", return_value=mock_store):
            from langflow.api.v1.flows import _provision_webhook_api_key

            key = await _provision_webhook_api_key(
                org_id="org-123",
                flow_id="flow-456",
                has_webhook=True,
            )

        assert key == "ADP-APICPRO-existing"
        mock_store.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_provision_returns_none_when_no_webhook(self):
        """When flow has no webhook component, return None and don't touch the store."""
        mock_store = AsyncMock()

        with patch("langflow.api.v1.flows.get_secret_store", return_value=mock_store):
            from langflow.api.v1.flows import _provision_webhook_api_key

            key = await _provision_webhook_api_key(
                org_id="org-123",
                flow_id="flow-456",
                has_webhook=False,
            )

        assert key is None
        mock_store.get.assert_not_called()
        mock_store.put.assert_not_called()
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `cd src/lfx && uv run pytest tests/unit/services/test_webhook_auth.py::TestWebhookKeyProvisioning -v`
Expected: FAIL — `ImportError: cannot import name '_provision_webhook_api_key'`

- [x] **Step 3: Add the provisioning function to flows.py**

Add the following imports near the top of `src/backend/base/langflow/api/v1/flows.py` (with the existing imports):

```python
from langflow.services.database.models.flow.utils import generate_webhook_api_key
from lfx.services.secret_store import get_secret_store
```

Add this function before the `_new_flow` function (around line 163):

```python
async def _provision_webhook_api_key(
    org_id: str,
    flow_id: str,
    has_webhook: bool,
) -> str | None:
    """Provision a webhook API key for a flow if it has a webhook component.

    Returns the API key (existing or newly generated), or None if no webhook.
    """
    if not has_webhook:
        return None

    store = get_secret_store()
    path = f"{org_id}/webhooks/{flow_id}"

    existing = await store.get(path)
    if existing and "api_key" in existing:
        return existing["api_key"]

    from datetime import datetime, timezone

    key = generate_webhook_api_key()
    await store.put(path, {
        "api_key": key,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return key
```

- [x] **Step 4: Wire provisioning into _new_flow**

In `src/backend/base/langflow/api/v1/flows.py`, in the `_new_flow` function, add after the line `db_flow.updated_at = datetime.now(timezone.utc)` (around line 272) and before the line `# Validate folder_id exists`:

```python
        # Provision webhook API key if flow has a webhook component
        webhook_component = get_webhook_component_in_flow(db_flow.data or {})
        db_flow.webhook = webhook_component is not None
        if db_flow.webhook and organization_id:
            await _provision_webhook_api_key(
                org_id=str(organization_id),
                flow_id=str(db_flow.id),
                has_webhook=True,
            )
```

- [x] **Step 5: Wire provisioning into update_flow**

In `src/backend/base/langflow/api/v1/flows.py`, in the `update_flow` function, after the existing lines (around line 518-519):

```python
        webhook_component = get_webhook_component_in_flow(db_flow.data)
        db_flow.webhook = webhook_component is not None
```

Add:

```python
        if db_flow.webhook and db_flow.organization_id:
            await _provision_webhook_api_key(
                org_id=str(db_flow.organization_id),
                flow_id=str(db_flow.id),
                has_webhook=True,
            )
```

- [x] **Step 6: Run the tests to verify they pass**

Run: `cd src/lfx && uv run pytest tests/unit/services/test_webhook_auth.py -v`
Expected: all 8 tests PASS

- [x] **Step 7: Commit**

```bash
git add src/backend/base/langflow/api/v1/flows.py src/lfx/tests/unit/services/test_webhook_auth.py
git commit -m "feat: auto-provision webhook API keys on flow create/update"
```

---

## Task 8: Enforce API Key on Webhook Endpoint

**Files:**
- Modify: `src/backend/base/langflow/api/v1/endpoints.py`
- Test: `src/lfx/tests/unit/services/test_webhook_auth.py` (append)

- [x] **Step 1: Write the failing test for webhook endpoint auth**

Append to `src/lfx/tests/unit/services/test_webhook_auth.py`:

```python
class TestWebhookEndpointAuth:
    @pytest.mark.asyncio
    async def test_validate_webhook_api_key_success(self):
        from langflow.api.v1.endpoints import _validate_webhook_api_key

        mock_store = AsyncMock()
        mock_store.get = AsyncMock(return_value={"api_key": "ADP-APICPRO-validkey123"})

        with patch("langflow.api.v1.endpoints.get_secret_store", return_value=mock_store):
            # Should not raise
            await _validate_webhook_api_key(
                org_id="org-123",
                flow_id="flow-456",
                provided_key="ADP-APICPRO-validkey123",
            )

    @pytest.mark.asyncio
    async def test_validate_webhook_api_key_invalid(self):
        from fastapi import HTTPException

        from langflow.api.v1.endpoints import _validate_webhook_api_key

        mock_store = AsyncMock()
        mock_store.get = AsyncMock(return_value={"api_key": "ADP-APICPRO-validkey123"})

        with patch("langflow.api.v1.endpoints.get_secret_store", return_value=mock_store):
            with pytest.raises(HTTPException) as exc_info:
                await _validate_webhook_api_key(
                    org_id="org-123",
                    flow_id="flow-456",
                    provided_key="ADP-APICPRO-wrongkey",
                )
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_validate_webhook_api_key_missing_from_store(self):
        from fastapi import HTTPException

        from langflow.api.v1.endpoints import _validate_webhook_api_key

        mock_store = AsyncMock()
        mock_store.get = AsyncMock(return_value=None)

        with patch("langflow.api.v1.endpoints.get_secret_store", return_value=mock_store):
            with pytest.raises(HTTPException) as exc_info:
                await _validate_webhook_api_key(
                    org_id="org-123",
                    flow_id="flow-456",
                    provided_key="ADP-APICPRO-anykey",
                )
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_validate_webhook_api_key_no_key_provided(self):
        from fastapi import HTTPException

        from langflow.api.v1.endpoints import _validate_webhook_api_key

        with pytest.raises(HTTPException) as exc_info:
            await _validate_webhook_api_key(
                org_id="org-123",
                flow_id="flow-456",
                provided_key=None,
            )
        assert exc_info.value.status_code == 401
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `cd src/lfx && uv run pytest tests/unit/services/test_webhook_auth.py::TestWebhookEndpointAuth -v`
Expected: FAIL — `ImportError: cannot import name '_validate_webhook_api_key'`

- [x] **Step 3: Add the validation function to endpoints.py**

Add this import near the top of `src/backend/base/langflow/api/v1/endpoints.py`:

```python
from lfx.services.secret_store import get_secret_store
```

Add this function before the `webhook_run_flow` function:

```python
async def _validate_webhook_api_key(
    org_id: str,
    flow_id: str,
    provided_key: str | None,
) -> None:
    """Validate a per-flow webhook API key against the secret store.

    Raises:
        HTTPException 401: If no key provided or no key provisioned for the flow.
        HTTPException 403: If the key is invalid.
        HTTPException 503: If the secret store is unreachable.
    """
    if not provided_key:
        raise HTTPException(status_code=401, detail="x-api-key header is required for webhook requests")

    try:
        store = get_secret_store()
        stored = await store.get(f"{org_id}/webhooks/{flow_id}")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Secret store unavailable") from exc

    if not stored or "api_key" not in stored:
        raise HTTPException(status_code=401, detail="No API key provisioned for this webhook")

    if not hmac.compare_digest(provided_key, stored["api_key"]):
        raise HTTPException(status_code=403, detail="Invalid API key")
```

Also add `import hmac` to the imports at the top of the file if not already present.

- [x] **Step 4: Wire validation into the webhook endpoint**

In `src/backend/base/langflow/api/v1/endpoints.py`, in the `webhook_run_flow` function, add right after the docstring (before the distributed execution path comment, around line 752):

```python
    # --- Per-flow API key validation ---
    provided_api_key = request.headers.get("x-api-key")
    # We need org_id from the flow; resolve it
    from langflow.services.database.models.flow.model import Flow as _FlowModel
    from langflow.services.deps import session_scope as _session_scope

    async with _session_scope() as _auth_session:
        _flow_record = await _auth_session.get(_FlowModel, flow.id)
        if _flow_record is None or _flow_record.organization_id is None:
            raise HTTPException(status_code=400, detail="Flow has no associated organization")
        _org_id = str(_flow_record.organization_id)

    await _validate_webhook_api_key(
        org_id=_org_id,
        flow_id=str(flow.id),
        provided_key=provided_api_key,
    )
    # --- End per-flow API key validation ---
```

- [x] **Step 5: Run the tests to verify they pass**

Run: `cd src/lfx && uv run pytest tests/unit/services/test_webhook_auth.py -v`
Expected: all 12 tests PASS

- [x] **Step 6: Commit**

```bash
git add src/backend/base/langflow/api/v1/endpoints.py src/lfx/tests/unit/services/test_webhook_auth.py
git commit -m "feat: enforce per-flow API key auth on webhook endpoint"
```

---

## Task 9: Update WebhookComponent to Display API Key

**Files:**
- Modify: `src/lfx/src/lfx/components/input_output/webhook.py`

- [x] **Step 1: Update the WebhookComponent**

Replace the contents of `src/lfx/src/lfx/components/input_output/webhook.py`:

```python
import json

from lfx.custom.custom_component.component import Component
from lfx.io import MultilineInput, Output
from lfx.schema.data import Data


class WebhookComponent(Component):
    display_name = "Webhook"
    documentation: str = "https://docs.langflow.org/component-webhook"
    name = "Webhook"
    icon = "webhook"

    inputs = [
        MultilineInput(
            name="data",
            display_name="Payload",
            info="Receives a payload from external systems via HTTP POST.",
            advanced=True,
        ),
        MultilineInput(
            name="curl",
            display_name="cURL",
            value="CURL_WEBHOOK",
            advanced=True,
            input_types=[],
        ),
        MultilineInput(
            name="endpoint",
            display_name="Endpoint",
            value="BACKEND_URL",
            advanced=False,
            copy_field=True,
            input_types=[],
        ),
        MultilineInput(
            name="api_key",
            display_name="API Key",
            info="Auto-generated API key required for webhook authentication. Include as x-api-key header.",
            advanced=False,
            copy_field=True,
            input_types=[],
        ),
    ]
    outputs = [
        Output(display_name="JSON", name="output_data", method="build_data"),
    ]

    def build_data(self) -> Data:
        message: str | Data = ""
        if not self.data:
            self.status = "No data provided."
            return Data(data={})
        try:
            my_data = self.data.replace('"\n"', '"\\n"')
            body = json.loads(my_data or "{}")
        except json.JSONDecodeError:
            body = {"payload": self.data}
            message = f"Invalid JSON payload. Please check the format.\n\n{self.data}"
        data = Data(data=body)
        if not message:
            message = data
        self.status = message
        return data
```

- [x] **Step 2: Verify the component loads without errors**

Run: `cd src/lfx && uv run python -c "from lfx.components.input_output.webhook import WebhookComponent; print('OK:', [i.name for i in WebhookComponent.inputs])"`
Expected: `OK: ['data', 'curl', 'endpoint', 'api_key']`

- [x] **Step 3: Commit**

```bash
git add src/lfx/src/lfx/components/input_output/webhook.py
git commit -m "feat: add api_key field to WebhookComponent for display"
```

---

## Task 10: Integration Test Against Real Vault

**Files:**
- Create: `src/lfx/tests/integration/services/test_vault_secret_store.py`

- [x] **Step 1: Write the integration test**

Create `src/lfx/tests/integration/services/test_vault_secret_store.py`:

```python
"""Integration tests for VaultSecretStore against a real Vault instance.

Requires a running Vault dev server:
    docker run --cap-add=IPC_LOCK \
      -e 'VAULT_DEV_ROOT_TOKEN_ID=myroot' \
      -e 'VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200' \
      -p 8200:8200 \
      --name vault-dev \
      hashicorp/vault

Run with: pytest tests/integration/services/test_vault_secret_store.py -v
"""

import os

import pytest

from lfx.services.secret_store.vault import VaultSecretStore

VAULT_ADDR = os.getenv("VAULT_ADDR", "http://localhost:8200")
VAULT_TOKEN = os.getenv("VAULT_TOKEN", "myroot")


@pytest.fixture
def vault_store():
    return VaultSecretStore(addr=VAULT_ADDR, token=VAULT_TOKEN, mount_point="secret")


@pytest.fixture(autouse=True)
async def cleanup(vault_store):
    """Clean up test secrets after each test."""
    yield
    # Best-effort cleanup
    try:
        keys = await vault_store.list("test-org/webhooks/")
        for key in keys:
            await vault_store.delete(f"test-org/webhooks/{key}")
    except Exception:
        pass


class TestVaultSecretStoreIntegration:
    @pytest.mark.asyncio
    async def test_put_and_get(self, vault_store):
        await vault_store.put("test-org/webhooks/flow-1", {"api_key": "ADP-APICPRO-testkey123"})
        result = await vault_store.get("test-org/webhooks/flow-1")
        assert result is not None
        assert result["api_key"] == "ADP-APICPRO-testkey123"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, vault_store):
        result = await vault_store.get("test-org/webhooks/nonexistent-flow")
        assert result is None

    @pytest.mark.asyncio
    async def test_overwrite(self, vault_store):
        await vault_store.put("test-org/webhooks/flow-2", {"api_key": "key-v1"})
        await vault_store.put("test-org/webhooks/flow-2", {"api_key": "key-v2"})
        result = await vault_store.get("test-org/webhooks/flow-2")
        assert result["api_key"] == "key-v2"

    @pytest.mark.asyncio
    async def test_delete(self, vault_store):
        await vault_store.put("test-org/webhooks/flow-3", {"api_key": "to-delete"})
        await vault_store.delete("test-org/webhooks/flow-3")
        result = await vault_store.get("test-org/webhooks/flow-3")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, vault_store):
        await vault_store.delete("test-org/webhooks/never-existed")  # should not raise

    @pytest.mark.asyncio
    async def test_list(self, vault_store):
        await vault_store.put("test-org/webhooks/flow-a", {"api_key": "a"})
        await vault_store.put("test-org/webhooks/flow-b", {"api_key": "b"})
        keys = await vault_store.list("test-org/webhooks/")
        assert "flow-a" in keys
        assert "flow-b" in keys

    @pytest.mark.asyncio
    async def test_list_empty(self, vault_store):
        keys = await vault_store.list("test-org/empty-prefix/")
        assert keys == []

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, vault_store):
        """Keys from one org are not visible under another org's prefix."""
        await vault_store.put("org-A/webhooks/flow-1", {"api_key": "a"})
        await vault_store.put("org-B/webhooks/flow-1", {"api_key": "b"})

        keys_a = await vault_store.list("org-A/webhooks/")
        keys_b = await vault_store.list("org-B/webhooks/")

        assert "flow-1" in keys_a
        assert "flow-1" in keys_b

        result_a = await vault_store.get("org-A/webhooks/flow-1")
        result_b = await vault_store.get("org-B/webhooks/flow-1")
        assert result_a["api_key"] == "a"
        assert result_b["api_key"] == "b"

        # Cleanup extra org
        await vault_store.delete("org-A/webhooks/flow-1")
        await vault_store.delete("org-B/webhooks/flow-1")
```

- [x] **Step 2: Run the integration tests**

Run: `cd src/lfx && VAULT_ADDR=http://localhost:8200 VAULT_TOKEN=myroot uv run pytest tests/integration/services/test_vault_secret_store.py -v`
Expected: all 8 tests PASS (requires Vault running on localhost:8200)

- [x] **Step 3: Commit**

```bash
git add src/lfx/tests/integration/services/test_vault_secret_store.py
git commit -m "test: add integration tests for VaultSecretStore against real Vault"
```

---

## Task 11: Clean Up Webhook API Key on Flow Delete

**Files:**
- Modify: `src/backend/base/langflow/api/v1/flows.py`
- Test: `src/lfx/tests/unit/services/test_webhook_auth.py` (append)

- [x] **Step 1: Write the failing test for key cleanup on delete**

Append to `src/lfx/tests/unit/services/test_webhook_auth.py`:

```python
class TestWebhookKeyCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_deletes_key_from_store(self):
        mock_store = AsyncMock()
        mock_store.delete = AsyncMock()

        with patch("langflow.api.v1.flows.get_secret_store", return_value=mock_store):
            from langflow.api.v1.flows import _cleanup_webhook_api_key

            await _cleanup_webhook_api_key(org_id="org-123", flow_id="flow-456")

        mock_store.delete.assert_called_once_with("org-123/webhooks/flow-456")

    @pytest.mark.asyncio
    async def test_cleanup_tolerates_store_errors(self):
        mock_store = AsyncMock()
        mock_store.delete = AsyncMock(side_effect=Exception("Vault down"))

        with patch("langflow.api.v1.flows.get_secret_store", return_value=mock_store):
            from langflow.api.v1.flows import _cleanup_webhook_api_key

            # Should not raise — best-effort cleanup
            await _cleanup_webhook_api_key(org_id="org-123", flow_id="flow-456")
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `cd src/lfx && uv run pytest tests/unit/services/test_webhook_auth.py::TestWebhookKeyCleanup -v`
Expected: FAIL — `ImportError: cannot import name '_cleanup_webhook_api_key'`

- [x] **Step 3: Add the cleanup function**

Add to `src/backend/base/langflow/api/v1/flows.py`, after the `_provision_webhook_api_key` function:

```python
async def _cleanup_webhook_api_key(org_id: str, flow_id: str) -> None:
    """Best-effort delete of a flow's webhook API key from the secret store."""
    try:
        store = get_secret_store()
        await store.delete(f"{org_id}/webhooks/{flow_id}")
    except Exception:
        logger.warning(f"Failed to clean up webhook API key for flow {flow_id}")
```

- [x] **Step 4: Wire cleanup into the delete_flow function**

Find the `delete_flow` function in `src/backend/base/langflow/api/v1/flows.py` (around line 724). Add the cleanup call before the flow is deleted from the database. After the flow is fetched and before `await session.delete(db_flow)`, add:

```python
        # Clean up webhook API key from secret store
        if db_flow.webhook and db_flow.organization_id:
            await _cleanup_webhook_api_key(
                org_id=str(db_flow.organization_id),
                flow_id=str(db_flow.id),
            )
```

- [x] **Step 5: Run the tests to verify they pass**

Run: `cd src/lfx && uv run pytest tests/unit/services/test_webhook_auth.py -v`
Expected: all 14 tests PASS

- [x] **Step 6: Commit**

```bash
git add src/backend/base/langflow/api/v1/flows.py src/lfx/tests/unit/services/test_webhook_auth.py
git commit -m "feat: clean up webhook API key from secret store on flow delete"
```

---

## Task 12: Run Full Test Suite and Verify

- [x] **Step 1: Run all unit tests**

Run: `cd src/lfx && uv run pytest tests/unit/services/test_secret_store.py tests/unit/services/test_webhook_auth.py -v`
Expected: all tests PASS

- [x] **Step 2: Run integration tests (requires Vault)**

Run: `cd src/lfx && VAULT_ADDR=http://localhost:8200 VAULT_TOKEN=myroot uv run pytest tests/integration/services/test_vault_secret_store.py -v`
Expected: all tests PASS

- [x] **Step 3: Verify no regressions in existing tests**

Run: `cd src/lfx && uv run pytest tests/ -x --timeout=60`
Expected: no new failures

- [x] **Step 4: Final commit (if any fixups needed)**

```bash
git add -A
git commit -m "fix: address test suite feedback"
```

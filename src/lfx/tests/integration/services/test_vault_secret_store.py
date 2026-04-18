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

        # Cleanup extra orgs
        await vault_store.delete("org-A/webhooks/flow-1")
        await vault_store.delete("org-B/webhooks/flow-1")

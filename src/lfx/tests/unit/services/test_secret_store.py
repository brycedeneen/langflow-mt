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

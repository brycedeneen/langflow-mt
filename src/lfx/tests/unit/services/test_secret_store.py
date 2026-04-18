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

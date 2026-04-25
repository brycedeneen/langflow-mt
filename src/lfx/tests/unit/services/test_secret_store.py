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
        seen: set[str] = set()
        for key in self._store:
            if not key.startswith(prefix):
                continue
            rest = key[len(prefix):]
            if not rest:
                continue
            head, sep, _ = rest.partition("/")
            seen.add(head + ("/" if sep else ""))
        return sorted(seen)


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
        # Immediate children of "org1/webhooks/" are leaf names (no trailing /).
        result = await store.list("org1/webhooks/")
        assert result == ["flow1", "flow2"]

    @pytest.mark.asyncio
    async def test_list_empty_prefix(self):
        store = ConcreteSecretStore()
        result = await store.list("nonexistent/")
        assert result == []

    @pytest.mark.asyncio
    async def test_list_returns_directory_markers_for_subdirs(self):
        """Sub-directory entries end with `/`; leaves don't."""
        store = ConcreteSecretStore()
        await store.put("a/b/c", {"v": 1})
        await store.put("a/b/d", {"v": 2})
        await store.put("a/e", {"v": 3})
        # At "a/", children are "b/" (subdir) and "e" (leaf).
        assert await store.list("a/") == ["b/", "e"]
        # At "a/b/", both children are leaves.
        assert await store.list("a/b/") == ["c", "d"]

    @pytest.mark.asyncio
    async def test_list_excludes_exact_match_prefix(self):
        """A key that equals the prefix is not its own child."""
        store = ConcreteSecretStore()
        await store.put("a/b/", {"v": 1})  # the directory itself
        await store.put("a/b/c", {"v": 2})
        # "a/b/" is the directory; "c" is the only child.
        assert await store.list("a/b/") == ["c"]

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
        ) as mock_read:
            result = await store.get("org1/webhooks/flow1")
            assert result == {"api_key": "ADP-APICPRO-abc123"}
            mock_read.assert_called_once_with(
                path="org1/webhooks/flow1",
                mount_point="secret",
                raise_on_deleted_version=False,
            )

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
    async def test_get_soft_deleted_version_returns_none(self):
        store = self._make_store()
        mock_response = {
            "data": {
                "data": None,
                "metadata": {"deletion_time": "2026-04-19T00:00:00Z"},
            }
        }
        with patch.object(
            store._client.secrets.kv.v2, "read_secret_version", return_value=mock_response
        ):
            result = await store.get("org1/webhooks/flow1")
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


from lfx.services.secret_store.factory import get_secret_store, InMemorySecretStore


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
        assert isinstance(store, InMemorySecretStore)

    def test_unknown_backend_raises(self):
        settings = SecretStoreSettings(SECRET_STORE_BACKEND="unknown_backend")
        with pytest.raises(ValueError, match="Unknown secret store backend"):
            get_secret_store(settings)

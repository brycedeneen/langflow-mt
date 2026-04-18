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

"""HashiCorp Vault KV v2 implementation of SecretStore."""

from __future__ import annotations

import asyncio

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
                raise_on_deleted_version=False,
            )
        except InvalidPath:
            return None
        return (response.get("data") or {}).get("data")

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

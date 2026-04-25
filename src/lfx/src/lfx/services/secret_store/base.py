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
        """List immediate children under a prefix (KV v2 LIST semantics).

        Returns relative names — sub-directory entries end with ``/``, leaf
        entries do not. Callers walking deeper structure must recurse explicitly.

        Example:
            Store has keys: ``["a/b/c", "a/b/d", "a/e"]``.
            ``store.list("a/")``  → ``["b/", "e"]``
            ``store.list("a/b/")`` → ``["c", "d"]``
        """

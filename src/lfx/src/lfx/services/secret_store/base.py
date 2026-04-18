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

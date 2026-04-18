"""Pluggable secret store service."""

from lfx.services.secret_store.base import SecretStore
from lfx.services.secret_store.factory import get_secret_store

__all__ = ["SecretStore", "get_secret_store"]

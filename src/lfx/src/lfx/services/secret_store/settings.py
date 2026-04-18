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

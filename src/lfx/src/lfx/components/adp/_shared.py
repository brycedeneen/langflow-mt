"""Shared helpers for ADP components: connection object, token fetch, mTLS client."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import httpx

DEFAULT_API_BASE_URL = "https://api.adp.com"
DEFAULT_MCP_BASE_URL = "https://mcp.adp.com/mcp"  # placeholder until real URL known
DEFAULT_TOKEN_URL = "https://accounts.adp.com/auth/oauth/v2/token"
TOKEN_TTL_SECONDS = 55 * 60  # 55 minutes


@dataclass
class ADPConnection:
    """Shared connection state produced by ADPAuthComponent, consumed by API/MCP components.

    Not frozen: token and expiry are mutated by the token-fetch helper.
    """

    client_id: str
    client_secret: str
    cert_source: Literal["path", "pem"]
    cert_path: str | None = None
    key_path: str | None = None
    cert_pem: str | None = None
    key_pem: str | None = None
    api_base_url: str = DEFAULT_API_BASE_URL
    mcp_base_url: str = DEFAULT_MCP_BASE_URL
    token_url: str = DEFAULT_TOKEN_URL
    access_token: str | None = None
    token_expires_at: datetime | None = None


def build_mtls_httpx_client(conn: "ADPConnection", *, timeout: float = 30.0) -> httpx.AsyncClient:
    """Build an httpx.AsyncClient configured with mTLS from an ADPConnection.

    For ``cert_source="path"`` the cert/key paths are used directly.
    For ``cert_source="pem"`` the PEM contents are written to temp files (0600)
    and those paths are handed to httpx. Temp files are cleaned up when the
    returned client is closed.
    """
    if conn.cert_source == "path":
        if not conn.cert_path or not conn.key_path:
            msg = "cert_path and key_path are required when cert_source='path'"
            raise ValueError(msg)
        cert_tuple = (conn.cert_path, conn.key_path)
        temp_paths: list[Path] = []
    elif conn.cert_source == "pem":
        if not conn.cert_pem or not conn.key_pem:
            msg = "cert_pem and key_pem are required when cert_source='pem'"
            raise ValueError(msg)
        cert_tuple, temp_paths = _write_pem_temp_files(conn.cert_pem, conn.key_pem)
    else:
        msg = f"Unknown cert_source: {conn.cert_source!r}"
        raise ValueError(msg)

    client = httpx.AsyncClient(cert=cert_tuple, timeout=timeout)
    # Attach temp paths for cleanup on close
    client._adp_temp_cert_paths = temp_paths  # noqa: SLF001 - internal marker

    original_aclose = client.aclose

    async def aclose_with_cleanup() -> None:
        try:
            await original_aclose()
        finally:
            for p in temp_paths:
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    pass

    client.aclose = aclose_with_cleanup  # type: ignore[method-assign]
    return client


def _write_pem_temp_files(cert_pem: str, key_pem: str) -> tuple[tuple[str, str], list[Path]]:
    """Write cert/key PEM strings to 0600 temp files; return (cert,key) paths + cleanup list."""
    cert_path = _write_secure_tempfile(cert_pem, suffix=".pem")
    key_path = _write_secure_tempfile(key_pem, suffix=".pem")
    return (str(cert_path), str(key_path)), [cert_path, key_path]


def _write_secure_tempfile(content: str, *, suffix: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=suffix, prefix="adp-")
    try:
        os.write(fd, content.encode("utf-8"))
    finally:
        os.close(fd)
    path = Path(name)
    path.chmod(0o600)
    return path

"""Shared helpers for ADP components: connection object, token fetch, mTLS client."""

from __future__ import annotations

import contextlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import httpx

if TYPE_CHECKING:
    from datetime import datetime

DEFAULT_API_BASE_URL = "https://api.adp.com"
DEFAULT_MCP_BASE_URL = "https://mcp.adp.com/mcp"  # placeholder until real URL known
DEFAULT_TOKEN_URL = "https://accounts.adp.com/auth/oauth/v2/token"  # noqa: S105
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


class _MTLSClient(httpx.AsyncClient):
    """httpx AsyncClient that unlinks temp PEM files on close.

    Overrides both ``aclose()`` and ``__aexit__()`` so temp files are cleaned up
    whether the caller closes explicitly or uses the client as an async context
    manager.
    """

    def __init__(self, *args, temp_cert_paths: list[Path] | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._temp_cert_paths: list[Path] = temp_cert_paths or []

    @property
    def _adp_temp_cert_paths(self) -> list[Path]:
        """Back-compat alias for tests written against the previous API."""
        return self._temp_cert_paths

    async def _cleanup_temp_files(self) -> None:
        for p in self._temp_cert_paths:
            with contextlib.suppress(OSError):
                p.unlink(missing_ok=True)

    async def aclose(self) -> None:
        try:
            await super().aclose()
        finally:
            await self._cleanup_temp_files()

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        try:
            await super().__aexit__(exc_type, exc_value, traceback)
        finally:
            await self._cleanup_temp_files()


def build_mtls_httpx_client(conn: ADPConnection, *, timeout: float = 30.0) -> httpx.AsyncClient:
    """Build an httpx.AsyncClient configured with mTLS from an ADPConnection.

    For ``cert_source="path"`` the cert/key paths are used directly.
    For ``cert_source="pem"`` the PEM contents are written to temp files (0600)
    and those paths are handed to httpx. Temp files are cleaned up when the
    returned client is closed (explicit aclose OR async-context-manager exit).
    """
    if conn.cert_source == "path":
        if not conn.cert_path or not conn.key_path:
            msg = "cert_path and key_path are required when cert_source='path'"
            raise ValueError(msg)
        cert_tuple: tuple[str, str] = (conn.cert_path, conn.key_path)
        temp_paths: list[Path] = []
    elif conn.cert_source == "pem":
        if not conn.cert_pem or not conn.key_pem:
            msg = "cert_pem and key_pem are required when cert_source='pem'"
            raise ValueError(msg)
        cert_tuple, temp_paths = _write_pem_temp_files(conn.cert_pem, conn.key_pem)
    else:
        msg = f"Unknown cert_source: {conn.cert_source!r}"
        raise ValueError(msg)

    return _MTLSClient(cert=cert_tuple, timeout=timeout, temp_cert_paths=temp_paths)


def _write_pem_temp_files(cert_pem: str, key_pem: str) -> tuple[tuple[str, str], list[Path]]:
    """Write cert/key PEM strings to 0600 temp files; return (cert,key) paths + cleanup list."""
    cert_path = _write_secure_tempfile(cert_pem, suffix=".pem")
    key_path = _write_secure_tempfile(key_pem, suffix=".pem")
    return (str(cert_path), str(key_path)), [cert_path, key_path]


def _write_secure_tempfile(content: str, *, suffix: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=suffix, prefix="adp-")
    path = Path(name)
    try:
        os.write(fd, content.encode("utf-8"))
    except BaseException:
        os.close(fd)
        path.unlink(missing_ok=True)
        raise
    else:
        os.close(fd)
    # mkstemp creates at 0600; chmod is belt-and-suspenders documentation of intent.
    path.chmod(0o600)
    return path

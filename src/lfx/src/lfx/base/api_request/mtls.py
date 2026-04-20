"""Shared mTLS helpers — PEM normalization, secure temp-file writing, and
an async context manager that provides the (cert, key[, password]) tuple
that httpx.AsyncClient(cert=...) expects.

Extracted from src/lfx/src/lfx/components/adp/_shared.py so the stock
APIRequest component can share the same primitives.
"""

from __future__ import annotations

import contextlib
import os
import re
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path


def _normalize_pem(pem: str) -> str:
    """Fix common PEM formatting issues from pasting into text fields.

    Handles: missing newlines around headers, \\n literals, extra whitespace.
    """
    pem = pem.strip()
    pem = pem.replace("\\n", "\n")
    pem = pem.replace("\r\n", "\n").replace("\r", "\n")

    def _reformat_block(match: re.Match) -> str:
        header = match.group(1)
        body = match.group(2)
        footer = match.group(3)
        body_clean = re.sub(r"\s+", "", body)
        lines = [body_clean[i : i + 64] for i in range(0, len(body_clean), 64)]
        return header + "\n" + "\n".join(lines) + "\n" + footer

    pem = re.sub(
        r"(-----BEGIN [A-Z0-9 ]+-----)\s*(.*?)\s*(-----END [A-Z0-9 ]+-----)",
        _reformat_block,
        pem,
        flags=re.DOTALL,
    )
    if not pem.endswith("\n"):
        pem += "\n"
    return pem


def _write_secure_tempfile(content: str, *, suffix: str) -> Path:
    """Write `content` to a new 0600 temp file and return its path."""
    fd, name = tempfile.mkstemp(suffix=suffix, prefix="langflow-mtls-")
    path = Path(name)
    try:
        os.write(fd, content.encode("utf-8"))
    except BaseException:
        os.close(fd)
        path.unlink(missing_ok=True)
        raise
    else:
        os.close(fd)
    # mkstemp creates at 0600; chmod is belt-and-suspenders.
    path.chmod(0o600)
    return path


@asynccontextmanager
async def mtls_temp_files(
    cert_pem: str | None,
    key_pem: str | None,
    key_password: str | None = None,
) -> AsyncIterator[tuple[str, str] | tuple[str, str, str] | None]:
    """Yield the httpx `cert=` argument built from PEM strings.

    - Yields ``None`` when both cert_pem and key_pem are empty/None (no mTLS).
    - Yields ``(cert_path, key_path)`` when both PEMs are provided and no password.
    - Yields ``(cert_path, key_path, key_password)`` when password is provided.

    Temp files are 0600 and are unlinked on context exit (success or failure).
    """
    if not cert_pem and not key_pem:
        yield None
        return

    if not cert_pem or not key_pem:
        msg = (
            "mTLS requires both a client certificate and a client key. "
            "Provide both cert_pem and key_pem."
        )
        raise ValueError(msg)

    cert_path = _write_secure_tempfile(_normalize_pem(cert_pem), suffix=".pem")
    key_path = _write_secure_tempfile(_normalize_pem(key_pem), suffix=".pem")
    try:
        if key_password:
            yield (str(cert_path), str(key_path), key_password)
        else:
            yield (str(cert_path), str(key_path))
    finally:
        with contextlib.suppress(OSError):
            cert_path.unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            key_path.unlink(missing_ok=True)

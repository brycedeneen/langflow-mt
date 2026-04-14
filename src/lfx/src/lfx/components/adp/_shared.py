"""Shared helpers for ADP components: connection object, token fetch, mTLS client."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

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

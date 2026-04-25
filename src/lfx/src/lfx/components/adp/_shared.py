"""Shared helpers for ADP components: connection object, token fetch, mTLS client."""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx

from lfx.base.api_request.mtls import mtls_temp_files

DEFAULT_API_BASE_URL = "https://api.adp.com"
DEFAULT_MCP_BASE_URL = "https://mcp.adp.com/mcp"  # placeholder until real URL known
DEFAULT_TOKEN_URL = "https://accounts.adp.com/auth/oauth/v2/token"  # noqa: S105
TOKEN_TTL_SECONDS = 55 * 60  # 55 minutes
ALLOWED_ADP_HOST = "adp.com"
ALLOWED_ADP_HOST_SUFFIX = ".adp.com"


def validate_adp_url(url: str, *, field_name: str) -> str:
    """Require https + host is exactly 'adp.com' or ends in '.adp.com'.

    Rejects off-allowlist hosts, non-https schemes, URLs with userinfo, and
    missing/malformed hosts. Returns the url unchanged on success.
    """
    if not isinstance(url, str) or not url:
        msg = f"{field_name} must be a non-empty https URL on *.adp.com"
        raise ValueError(msg)
    try:
        parts = urlsplit(url)
    except ValueError as e:
        msg = f"{field_name} is not a valid URL: {e}"
        raise ValueError(msg) from e
    if parts.scheme != "https":
        msg = f"{field_name} must use https scheme (got {parts.scheme!r})"
        raise ValueError(msg)
    if "@" in (parts.netloc or ""):
        msg = f"{field_name} must not contain userinfo"
        raise ValueError(msg)
    host = (parts.hostname or "").lower()
    if not host:
        msg = f"{field_name} is missing a host"
        raise ValueError(msg)
    if host != ALLOWED_ADP_HOST and not host.endswith(ALLOWED_ADP_HOST_SUFFIX):
        msg = f"{field_name} host {host!r} is not on the ADP allowlist (*.adp.com)"
        raise ValueError(msg)
    return url


@dataclass
class ADPConnection:
    """Shared connection state produced by ADPAuthComponent, consumed by API/MCP components.

    Not frozen: token and expiry are mutated by the token-fetch helper.
    """

    client_id: str
    client_secret: str
    cert_pem: str
    key_pem: str
    api_base_url: str = DEFAULT_API_BASE_URL
    mcp_base_url: str = DEFAULT_MCP_BASE_URL
    token_url: str = DEFAULT_TOKEN_URL
    access_token: str | None = None
    token_expires_at: datetime | None = None


@asynccontextmanager
async def build_mtls_httpx_client(
    conn: ADPConnection,
    *,
    timeout: float = 30.0,
) -> AsyncIterator[httpx.AsyncClient]:
    """Async context manager yielding an httpx.AsyncClient configured with mTLS
    using the connection's PEMs. Temp files for cert/key are 0600 and are
    unlinked on exit.
    """
    if not conn.cert_pem or not conn.key_pem:
        msg = "ADPConnection requires both cert_pem and key_pem."
        raise ValueError(msg)

    async with mtls_temp_files(conn.cert_pem, conn.key_pem) as cert_tuple:
        async with httpx.AsyncClient(cert=cert_tuple, timeout=timeout) as client:
            yield client


async def fetch_token(conn: ADPConnection, *, force: bool = False) -> None:
    """Ensure ``conn.access_token`` is populated and non-expired.

    Uses the in-memory cache on ``conn``. Sets ``token_expires_at`` to now + 55 min
    on success (ignoring ADP's ``expires_in`` — 55 min is our explicit contract).
    On non-2xx responses, raises RuntimeError with the response body attached so
    callers can surface ADP's OAuth error payload to users.
    """
    if not force and _token_is_fresh(conn):
        return

    async with build_mtls_httpx_client(conn) as client:
        response = await _post_token_request(client, conn)

    if response.status_code >= 400:  # noqa: PLR2004
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        msg = f"ADP token endpoint returned {response.status_code}: {detail}"
        raise RuntimeError(msg)

    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        msg = f"ADP token response missing access_token: {payload}"
        raise RuntimeError(msg)

    conn.access_token = access_token
    conn.token_expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=TOKEN_TTL_SECONDS)


def _token_is_fresh(conn: ADPConnection) -> bool:
    if not conn.access_token or not conn.token_expires_at:
        return False
    return datetime.now(tz=timezone.utc) < conn.token_expires_at


async def _post_token_request(client: httpx.AsyncClient, conn: ADPConnection) -> httpx.Response:
    """Isolated for easy mocking in tests."""
    return await client.post(
        conn.token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": conn.client_id,
            "client_secret": conn.client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    expires_at: float
    value: Any


class RequestCache:
    """Read-through cache for ADP GETs, scoped to a single build_tools() call.

    Closure-scoped, so also implicitly per-ADPConnection: two ADP Tools components
    in one flow get two independent caches with no cross-tenant leakage.
    Reads only — writes never consult or populate this cache.
    """

    def __init__(self, *, ttl_seconds: float = 30.0, max_entries: int = 128) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._entries: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}

    @staticmethod
    def make_key(method: str, url: str, query: Mapping[str, Any] | None = None) -> str:
        # Resolved URL (post path-substitution), sorted query items, no Authorization.
        items = sorted((query or {}).items())
        return f"{method.upper()} {url}?{urlencode(items, doseq=True)}"

    async def get_or_fetch(self, key: str, fetch: Callable[[], Awaitable[Any]]) -> Any:
        now = time.monotonic()
        entry = self._entries.get(key)
        if entry and entry.expires_at > now:
            self._entries.move_to_end(key)
            return entry.value
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            entry = self._entries.get(key)
            if entry and entry.expires_at > time.monotonic():
                return entry.value
            value = await fetch()
            self._store(key, value)
            return value

    def peek(self, key: str) -> Any | None:
        """Lock-free read; returns the cached value if present and not expired, else None.

        Safe in single-task asyncio: there is no await between the dict lookup
        and the returned value. Concurrent peekers may both observe a miss
        and proceed to acquire ``lock_for(key)`` to serialize the fetch.
        """
        entry = self._entries.get(key)
        if entry and entry.expires_at > time.monotonic():
            self._entries.move_to_end(key)
            return entry.value
        return None

    def lock_for(self, key: str) -> asyncio.Lock:
        """Get (or create) the per-key lock for serialized fetches on a cold miss."""
        return self._locks.setdefault(key, asyncio.Lock())

    def put(self, key: str, value: Any) -> None:
        """Store a value under key. Caller is responsible for serialization
        (typically via ``async with cache.lock_for(key):``).
        """
        self._store(key, value)

    def _store(self, key: str, value: Any) -> None:
        self._entries[key] = _CacheEntry(expires_at=time.monotonic() + self._ttl, value=value)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max:
            evicted_key, _ = self._entries.popitem(last=False)
            # Drop the lock alongside the entry. Edge case: if a fetch is in flight
            # for `evicted_key` when this fires, a later concurrent caller could
            # create a new lock and run a parallel fetch (mild thundering-herd
            # under capacity churn). Acceptable here because (a) the cache is
            # closure-scoped to one build_tools() call and bounded by max_entries,
            # (b) ADP read patterns rarely exceed max_entries unique URLs per turn.
            self._locks.pop(evicted_key, None)


HTTP_UNAUTHORIZED = 401
HTTP_CLIENT_ERROR_MIN = 400


async def cached_get_json(
    *,
    client: httpx.AsyncClient,
    cache: RequestCache,
    url: str,
    headers: Mapping[str, str],
    params: Mapping[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Cache-aware GET returning parsed JSON.

    Caches the parsed JSON dict on 2xx. On any error (HTTP status >= 400 or
    a non-JSON 2xx body), returns ``{"error": ..., "status_code": ...}`` and
    does NOT cache. Bearer tokens in ``headers`` are passed through but never
    participate in the key.

    Concurrency: cold-miss callers serialize on the per-key lock so a single
    HTTP request is fired even when many coroutines target the same key
    simultaneously. The 401-refresh dance is the caller's responsibility — this
    helper does not retry.
    """
    key = RequestCache.make_key("GET", url, params)

    # Fast path — lock-free peek.
    cached = cache.peek(key)
    if cached is not None:
        return cached

    # Cold miss. Serialize on the per-key lock so only one fetcher fires.
    async with cache.lock_for(key):
        cached = cache.peek(key)
        if cached is not None:
            return cached

        response = await client.request(
            method="GET",
            url=url,
            headers=dict(headers),
            params=dict(params or {}),
            timeout=timeout,
        )
        if response.status_code >= HTTP_CLIENT_ERROR_MIN:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            return {"error": detail, "status_code": response.status_code}

        try:
            result = response.json()
        except ValueError:
            return {"error": response.text, "status_code": response.status_code}

        cache.put(key, result)
        return result

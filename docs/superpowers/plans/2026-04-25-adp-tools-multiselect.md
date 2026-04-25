# ADP Tools Multi-Select Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 29 `ADP*ToolsComponent` classes with one `ADPToolsComponent` whose `MultiselectInput` lets the user pick which tile groups to expose, while introducing a per-build read cache that eliminates duplicate ADP API GETs across tools.

**Architecture:** Each existing `adp_*_tools.py` file is refactored from a `Component` subclass into a module-level `build_<tile>_tools(connection, request_cache) -> list[Tool]` function. A new `adp_tools.py` holds the unified component, a `{label: builder}` registry, and the `MultiselectInput`. A new closure-scoped `RequestCache` in `_shared.py` is created once per `build_tools()` call and threaded into every selected tile's builder; reads consult it via `cached_get_json`, writes bypass it.

**Tech Stack:** Python 3.11+, `httpx`, `langchain_core.tools.StructuredTool`, `pydantic`, `lfx.io` (`HandleInput`, `MultiselectInput`, `Output`), `pytest`, `pytest-asyncio`.

**Spec:** [`docs/superpowers/specs/2026-04-25-adp-tools-multiselect-design.md`](../specs/2026-04-25-adp-tools-multiselect-design.md)

**Test environment note:** Per `reference_lfx_test_env.md`, the `src/lfx` test suite needs `LFX_TEST_ALLOW_LANGFLOW=1` when run from the repo-level venv. Every `pytest` command below assumes this env var is set. Set it once for your shell session: `export LFX_TEST_ALLOW_LANGFLOW=1`.

**Commit hygiene reminder:** Per `feedback_subagent_commit_hygiene.md`, every `git add` lists explicit paths — never `-A`, `-a`, or `.` — to avoid catching unrelated WIP files.

---

## Task 1: Add `RequestCache` to `_shared.py`

Closure-scoped read-only cache with TTL, LRU eviction, and per-key `asyncio.Lock` for thundering-herd prevention.

**Files:**
- Modify: `src/lfx/src/lfx/components/adp/_shared.py` (add `RequestCache`, `_CacheEntry`)
- Create: `src/lfx/tests/unit/components/adp/test_request_cache.py`

- [ ] **Step 1: Write the failing tests**

Create `src/lfx/tests/unit/components/adp/test_request_cache.py`:

```python
"""Tests for RequestCache — closure-scoped read cache for ADP tools."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from lfx.components.adp._shared import RequestCache


@pytest.mark.asyncio
async def test_get_then_get_same_key_hits_once():
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    calls = 0

    async def fetch():
        nonlocal calls
        calls += 1
        return {"value": 42}

    key = RequestCache.make_key("GET", "https://api.adp.com/hr/v2/workers/X", None)
    first = await cache.get_or_fetch(key, fetch)
    second = await cache.get_or_fetch(key, fetch)

    assert first == {"value": 42}
    assert second == {"value": 42}
    assert calls == 1


@pytest.mark.asyncio
async def test_ttl_expiry_refetches():
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    calls = 0

    async def fetch():
        nonlocal calls
        calls += 1
        return {"value": calls}

    key = RequestCache.make_key("GET", "https://api.adp.com/hr/v2/workers/X", None)
    base = time.monotonic()
    with patch("lfx.components.adp._shared.time.monotonic", side_effect=[base, base, base + 31, base + 31, base + 31]):
        first = await cache.get_or_fetch(key, fetch)
        second = await cache.get_or_fetch(key, fetch)

    assert first == {"value": 1}
    assert second == {"value": 2}
    assert calls == 2


@pytest.mark.asyncio
async def test_different_associate_oids_do_not_collide():
    """Regression guard: two employees must never share a cache entry."""
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    fetch_calls: list[str] = []

    def make_fetcher(label: str):
        async def fetch():
            fetch_calls.append(label)
            return {"oid": label}
        return fetch

    url_a = "https://api.adp.com/hr/v2/workers/G3ABC"
    url_b = "https://api.adp.com/hr/v2/workers/G3XYZ"
    key_a = RequestCache.make_key("GET", url_a, None)
    key_b = RequestCache.make_key("GET", url_b, None)

    assert key_a != key_b
    result_a = await cache.get_or_fetch(key_a, make_fetcher("A"))
    result_b = await cache.get_or_fetch(key_b, make_fetcher("B"))
    result_a2 = await cache.get_or_fetch(key_a, make_fetcher("A2"))

    assert result_a == {"oid": "A"}
    assert result_b == {"oid": "B"}
    assert result_a2 == {"oid": "A"}  # cached from first call
    assert fetch_calls == ["A", "B"]


@pytest.mark.asyncio
async def test_concurrent_get_or_fetch_locks_per_key():
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    in_flight = 0
    max_in_flight = 0

    async def fetch():
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return {"value": "ok"}

    key = RequestCache.make_key("GET", "https://api.adp.com/hr/v2/workers/X", None)
    results = await asyncio.gather(*[cache.get_or_fetch(key, fetch) for _ in range(10)])

    assert all(r == {"value": "ok"} for r in results)
    assert max_in_flight == 1


@pytest.mark.asyncio
async def test_lru_eviction_at_max():
    cache = RequestCache(ttl_seconds=30, max_entries=2)

    async def fetch_a():
        return "a"

    async def fetch_b():
        return "b"

    async def fetch_c():
        return "c"

    await cache.get_or_fetch("A", fetch_a)
    await cache.get_or_fetch("B", fetch_b)
    await cache.get_or_fetch("C", fetch_c)  # should evict "A"

    # Re-fetching "A" calls fetch_a_again because A was evicted on the third store
    calls = 0

    async def fetch_a_again():
        nonlocal calls
        calls += 1
        return "a-fresh"

    result = await cache.get_or_fetch("A", fetch_a_again)
    assert result == "a-fresh"
    assert calls == 1
    # B was evicted on refetch (C is newer in LRU order)
    assert "B" not in cache._entries
    assert "C" in cache._entries
    assert "A" in cache._entries


def test_bearer_token_not_in_key():
    """Regression guard: token rotates on 401 refresh; must not invalidate cache."""
    key1 = RequestCache.make_key("GET", "https://api.adp.com/hr/v2/workers/X", None)
    key2 = RequestCache.make_key("GET", "https://api.adp.com/hr/v2/workers/X", None)
    assert key1 == key2


def test_query_params_part_of_key():
    key1 = RequestCache.make_key("GET", "https://api.adp.com/hr/v2/workers", {"limit": 10})
    key2 = RequestCache.make_key("GET", "https://api.adp.com/hr/v2/workers", {"limit": 50})
    assert key1 != key2


def test_query_params_order_normalized():
    key1 = RequestCache.make_key("GET", "https://api.adp.com/hr/v2/workers", {"limit": 10, "offset": 0})
    key2 = RequestCache.make_key("GET", "https://api.adp.com/hr/v2/workers", {"offset": 0, "limit": 10})
    assert key1 == key2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/brycedeneen/dev/langflow && LFX_TEST_ALLOW_LANGFLOW=1 uv run --project src/lfx pytest src/lfx/tests/unit/components/adp/test_request_cache.py -v`

Expected: All tests fail with `ImportError: cannot import name 'RequestCache' from 'lfx.components.adp._shared'`.

- [ ] **Step 3: Implement `RequestCache` in `_shared.py`**

Open `src/lfx/src/lfx/components/adp/_shared.py`. At the top, add to existing imports (merge with what's already there — do not duplicate `httpx`, `dataclass`, etc.):

```python
import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping
from typing import Any
from urllib.parse import urlencode
```

Append at end of file (after existing helpers, before EOF):

```python
@dataclass
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

    def _store(self, key: str, value: Any) -> None:
        self._entries[key] = _CacheEntry(expires_at=time.monotonic() + self._ttl, value=value)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max:
            evicted_key, _ = self._entries.popitem(last=False)
            self._locks.pop(evicted_key, None)
```

Note: `dataclass` is already imported at the top of `_shared.py`. Confirm before adding the second import line.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/brycedeneen/dev/langflow && LFX_TEST_ALLOW_LANGFLOW=1 uv run --project src/lfx pytest src/lfx/tests/unit/components/adp/test_request_cache.py -v`

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/adp/_shared.py src/lfx/tests/unit/components/adp/test_request_cache.py
git commit -m "feat(adp): add RequestCache closure-scoped read cache"
```

---

## Task 2: Add `cached_get_json` helper

Thin async wrapper that builds a cache key from the resolved URL + params, fetches via the cache, and returns parsed JSON or `{"error": ..., "status_code": ...}` on failure. Reads only — writes never call this.

**Files:**
- Modify: `src/lfx/src/lfx/components/adp/_shared.py` (add `cached_get_json`, `HTTP_UNAUTHORIZED`, `HTTP_CLIENT_ERROR_MIN`)
- Modify: `src/lfx/tests/unit/components/adp/test_request_cache.py` (add `cached_get_json` tests)

- [ ] **Step 1: Write the failing test**

In `src/lfx/tests/unit/components/adp/test_request_cache.py`, update the top-of-file imports so they end up reading exactly:

```python
"""Tests for RequestCache and cached_get_json."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lfx.components.adp._shared import RequestCache, cached_get_json
```

Then append the following tests to the bottom of the file:

```python
@pytest.mark.asyncio
async def test_cached_get_json_caches_2xx_response():
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    response_payload = {"workers": [{"associateOID": "G3ABC"}]}
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = response_payload

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = mock_response

    url = "https://api.adp.com/hr/v2/workers/G3ABC"
    headers = {"Authorization": "Bearer T1"}

    first = await cached_get_json(client=client, cache=cache, url=url, headers=headers)
    second = await cached_get_json(client=client, cache=cache, url=url, headers=headers)

    assert first == response_payload
    assert second == response_payload
    assert client.request.await_count == 1


@pytest.mark.asyncio
async def test_cached_get_json_does_not_cache_errors():
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    error_response = MagicMock(spec=httpx.Response)
    error_response.status_code = 500
    error_response.json.return_value = {"message": "boom"}
    error_response.text = ""

    success_response = MagicMock(spec=httpx.Response)
    success_response.status_code = 200
    success_response.json.return_value = {"workers": []}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.side_effect = [error_response, success_response]

    url = "https://api.adp.com/hr/v2/workers/G3ABC"
    headers = {"Authorization": "Bearer T1"}

    first = await cached_get_json(client=client, cache=cache, url=url, headers=headers)
    second = await cached_get_json(client=client, cache=cache, url=url, headers=headers)

    assert first == {"error": {"message": "boom"}, "status_code": 500}
    assert second == {"workers": []}  # not served from cache; second request fired
    assert client.request.await_count == 2
```

- [ ] **Step 2: Run new tests to verify they fail**

Run: `cd /Users/brycedeneen/dev/langflow && LFX_TEST_ALLOW_LANGFLOW=1 uv run --project src/lfx pytest src/lfx/tests/unit/components/adp/test_request_cache.py::test_cached_get_json_caches_2xx_response src/lfx/tests/unit/components/adp/test_request_cache.py::test_cached_get_json_does_not_cache_errors -v`

Expected: ImportError on `cached_get_json`.

- [ ] **Step 3: Implement `cached_get_json`**

Append to `src/lfx/src/lfx/components/adp/_shared.py`:

```python
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

    Caches the parsed JSON dict on 2xx. On any error (>=400 or non-JSON),
    returns ``{"error": ..., "status_code": ...}`` and does NOT cache.
    Bearer tokens in ``headers`` are passed through but never participate in the key.
    """
    key = RequestCache.make_key("GET", url, params)

    async def _fetch() -> dict[str, Any]:
        response = await client.request(
            method="GET", url=url, headers=dict(headers), params=dict(params or {}), timeout=timeout,
        )
        if response.status_code >= HTTP_CLIENT_ERROR_MIN:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            return {"error": detail, "status_code": response.status_code}
        return response.json()

    # Two-step: peek the cache; if hit, return. If miss, fetch and only store on success.
    entry = cache._entries.get(key)
    if entry and entry.expires_at > time.monotonic():
        cache._entries.move_to_end(key)
        return entry.value

    result = await _fetch()
    if "error" not in result:
        # Re-use lock-protected store path via get_or_fetch with a no-op fetcher pattern:
        async def _return_existing() -> dict[str, Any]:
            return result
        return await cache.get_or_fetch(key, _return_existing)
    return result
```

Note: `cached_get_json` uses cache internals to skip storing errors. Acceptable tight coupling within `_shared.py`. The 401-refresh dance happens **outside** this helper — the per-tile `_fetch_*` wrappers handle 401s before delegating to `cached_get_json` (or call it twice on 401 with refreshed headers). See Task 3.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/brycedeneen/dev/langflow && LFX_TEST_ALLOW_LANGFLOW=1 uv run --project src/lfx pytest src/lfx/tests/unit/components/adp/test_request_cache.py -v`

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/adp/_shared.py src/lfx/tests/unit/components/adp/test_request_cache.py
git commit -m "feat(adp): add cached_get_json helper with 2xx-only caching"
```

---

## Task 3: Refactor `adp_worker_tools.py` (canonical READ tile)

The canonical pattern. All other read-heavy tiles follow this shape. Worker is the highest-payoff tile: 9 tools, 1 endpoint — caching here means an agent firing 5 worker-info tools on the same OID makes 1 API call instead of 5.

**Files:**
- Modify: `src/lfx/src/lfx/components/adp/adp_worker_tools.py` (delete `ADPWorkerToolsComponent`, add `build_worker_tools`)
- Modify: `src/lfx/tests/unit/components/adp/test_adp_worker_tools.py` (replace component-instantiation harness with direct builder calls)

- [ ] **Step 1: Update tests first (TDD)**

Replace the component-instantiation paths in `test_adp_worker_tools.py`. The file currently imports `ADPWorkerToolsComponent` and the `extract_*` helpers. After this task, `ADPWorkerToolsComponent` no longer exists; tests import `build_worker_tools` and call it with a fake connection + `RequestCache()`.

The full pattern for the test file rewrite:

```python
"""Tests for build_worker_tools."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_worker_tools import (
    build_worker_tools,
    extract_addresses,
    extract_business_communication,
    extract_compensation,
    extract_contact_information,
    extract_dates,
    extract_ids,
    extract_job,
    extract_name,
    extract_status,
)

# SAMPLE_WORKER_RESPONSE — keep verbatim from the existing test file.

# ... extract_* tests stay verbatim — they test pure functions, no component needed.


def _make_connection(*, access_token="T1", api_base_url="https://api.adp.com"):
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


@asynccontextmanager
async def _fake_mtls_client(mock_response):
    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = mock_response
    yield client


def _build_tools(connection):
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    return build_worker_tools(connection, cache), cache


@pytest.mark.asyncio
async def test_build_worker_tools_returns_nine_tools():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_tools(conn, cache)

    names = [t.name for t in tools]
    assert names == [
        "get_employee_name",
        "get_employee_addresses",
        "get_employee_contact_information",
        "get_employee_job",
        "get_employee_compensation",
        "get_employee_ids",
        "get_employee_dates",
        "get_employee_status",
        "get_employee_business_communication",
    ]


@pytest.mark.asyncio
async def test_get_employee_name_returns_expected_shape():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_tools(conn, cache)
    get_name = next(t for t in tools if t.name == "get_employee_name")

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = SAMPLE_WORKER_RESPONSE

    with patch(
        "lfx.components.adp.adp_worker_tools.build_mtls_httpx_client",
        return_value=_fake_mtls_client(response),
    ):
        result = await get_name.ainvoke({"associate_oid": "G3ABC"})

    assert result == {
        "legalName": {"firstName": "Jane", "middleName": "Marie", "lastName": "Doe"},
        "preferredName": {"firstName": "Janie", "lastName": "Doe"},
    }


@pytest.mark.asyncio
async def test_two_tools_same_oid_share_cache():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_tools(conn, cache)
    get_name = next(t for t in tools if t.name == "get_employee_name")
    get_compensation = next(t for t in tools if t.name == "get_employee_compensation")

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = SAMPLE_WORKER_RESPONSE

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_worker_tools.build_mtls_httpx_client", fake_client):
        await get_name.ainvoke({"associate_oid": "G3ABC"})
        await get_compensation.ainvoke({"associate_oid": "G3ABC"})

    # Cache: 1 GET to /hr/v2/workers/G3ABC, served from cache on second tool call.
    assert client.request.await_count == 1


@pytest.mark.asyncio
async def test_unauthorized_triggers_refresh_and_retry():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_tools(conn, cache)
    get_name = next(t for t in tools if t.name == "get_employee_name")

    unauthorized = MagicMock(spec=httpx.Response)
    unauthorized.status_code = 401

    success = MagicMock(spec=httpx.Response)
    success.status_code = 200
    success.json.return_value = SAMPLE_WORKER_RESPONSE

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.side_effect = [unauthorized, success]

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_worker_tools.build_mtls_httpx_client", fake_client), \
         patch("lfx.components.adp.adp_worker_tools.fetch_token", AsyncMock()) as fetch_token_mock:
        result = await get_name.ainvoke({"associate_oid": "G3ABC"})

    assert "legalName" in result
    fetch_token_mock.assert_awaited_once()
    assert client.request.await_count == 2


@pytest.mark.asyncio
async def test_error_response_not_cached():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_tools(conn, cache)
    get_name = next(t for t in tools if t.name == "get_employee_name")

    error = MagicMock(spec=httpx.Response)
    error.status_code = 500
    error.json.return_value = {"message": "boom"}
    error.text = ""

    success = MagicMock(spec=httpx.Response)
    success.status_code = 200
    success.json.return_value = SAMPLE_WORKER_RESPONSE

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.side_effect = [error, success]

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_worker_tools.build_mtls_httpx_client", fake_client):
        first = await get_name.ainvoke({"associate_oid": "G3ABC"})
        second = await get_name.ainvoke({"associate_oid": "G3ABC"})

    assert first.get("status_code") == 500
    assert "legalName" in second  # not served from cache; refetched
    assert client.request.await_count == 2
```

Preserve every existing extract_* test from the current file verbatim. Only the component-test paths change. Move SAMPLE_WORKER_RESPONSE near the top so it's reusable.

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd /Users/brycedeneen/dev/langflow && LFX_TEST_ALLOW_LANGFLOW=1 uv run --project src/lfx pytest src/lfx/tests/unit/components/adp/test_adp_worker_tools.py -v`

Expected: ImportError on `build_worker_tools`.

- [ ] **Step 3: Refactor `adp_worker_tools.py`**

Replace the file's content. Preserve every existing `extract_*` helper verbatim. Replace the component class with a module-level builder.

```python
"""Worker-data agent tools backed by GET /hr/v2/workers/{associateOID}."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from lfx.components.adp._shared import (
    HTTP_UNAUTHORIZED,
    ADPConnection,
    RequestCache,
    build_mtls_httpx_client,
    cached_get_json,
    fetch_token,
    validate_adp_url,
)
from lfx.field_typing import Tool


# Preserve verbatim from existing file:
def extract_name(worker: dict[str, Any]) -> dict[str, Any]: ...
def extract_addresses(worker: dict[str, Any]) -> dict[str, Any]: ...
def extract_contact_information(worker: dict[str, Any]) -> dict[str, Any]: ...
def extract_job(worker: dict[str, Any]) -> dict[str, Any]: ...
def _id_value(id_obj: dict[str, Any] | None) -> dict[str, Any] | None: ...
def extract_ids(worker: dict[str, Any]) -> dict[str, Any]: ...
_WORKER_DATE_FIELDS = (...)
def extract_dates(worker: dict[str, Any]) -> dict[str, Any]: ...
def extract_status(worker: dict[str, Any]) -> dict[str, Any]: ...
def extract_business_communication(worker: dict[str, Any]) -> dict[str, Any]: ...
def extract_compensation(worker: dict[str, Any]) -> dict[str, Any]: ...


class WorkerToolInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID (unique employee identifier)")


async def _fetch_worker(
    conn: ADPConnection,
    associate_oid: str,
    *,
    request_cache: RequestCache,
) -> dict[str, Any]:
    url = f"{conn.api_base_url}/hr/v2/workers/{associate_oid}"
    validate_adp_url(url, field_name="api_base_url")

    async with build_mtls_httpx_client(conn, timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {conn.access_token}"}
        result = await cached_get_json(client=client, cache=request_cache, url=url, headers=headers)
        if result.get("status_code") == HTTP_UNAUTHORIZED:
            await fetch_token(conn, force=True)
            headers["Authorization"] = f"Bearer {conn.access_token}"
            result = await cached_get_json(client=client, cache=request_cache, url=url, headers=headers)

    if "error" in result:
        return result
    workers = result.get("workers", [])
    if not workers:
        return {"error": "No worker found", "status_code": 404}
    return workers[0]


def build_worker_tools(connection: ADPConnection, request_cache: RequestCache) -> list[Tool]:
    async def _get_employee_name(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_name(worker)

    async def _get_employee_addresses(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_addresses(worker)

    async def _get_employee_contact_information(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_contact_information(worker)

    async def _get_employee_job(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_job(worker)

    async def _get_employee_compensation(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_compensation(worker)

    async def _get_employee_ids(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_ids(worker)

    async def _get_employee_dates(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_dates(worker)

    async def _get_employee_status(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_status(worker)

    async def _get_employee_business_communication(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_business_communication(worker)

    return [
        StructuredTool.from_function(
            name="get_employee_name",
            description="Get an employee's legal and preferred name by their ADP associate OID.",
            coroutine=_get_employee_name,
            args_schema=WorkerToolInput,
        ),
        StructuredTool.from_function(
            name="get_employee_addresses",
            description="Get an employee's legal address by their ADP associate OID.",
            coroutine=_get_employee_addresses,
            args_schema=WorkerToolInput,
        ),
        StructuredTool.from_function(
            name="get_employee_contact_information",
            description="Get an employee's contact information (emails, phone numbers) by their ADP associate OID.",
            coroutine=_get_employee_contact_information,
            args_schema=WorkerToolInput,
        ),
        StructuredTool.from_function(
            name="get_employee_job",
            description="Get an employee's job details (title, department, location, manager) by their ADP associate OID.",
            coroutine=_get_employee_job,
            args_schema=WorkerToolInput,
        ),
        StructuredTool.from_function(
            name="get_employee_compensation",
            description="Get an employee's compensation details (base pay, additional remunerations) by their ADP associate OID.",
            coroutine=_get_employee_compensation,
            args_schema=WorkerToolInput,
        ),
        StructuredTool.from_function(
            name="get_employee_ids",
            description="Get an employee's identifiers (associateOID, workerID, alternateIDs) by their ADP associate OID.",
            coroutine=_get_employee_ids,
            args_schema=WorkerToolInput,
        ),
        StructuredTool.from_function(
            name="get_employee_dates",
            description=(
                "Get an employee's lifecycle dates (first hire, original hire, rehire, "
                "termination, retirement, leave-return, etc.) by their ADP associate OID."
            ),
            coroutine=_get_employee_dates,
            args_schema=WorkerToolInput,
        ),
        StructuredTool.from_function(
            name="get_employee_status",
            description=(
                "Get an employee's current worker status (active/terminated/leave), "
                "status reason, and effective date by their ADP associate OID."
            ),
            coroutine=_get_employee_status,
            args_schema=WorkerToolInput,
        ),
        StructuredTool.from_function(
            name="get_employee_business_communication",
            description=(
                "Get an employee's business communication channels (work email, work phone, "
                "work mobile) by their ADP associate OID. Distinct from personal contact info."
            ),
            coroutine=_get_employee_business_communication,
            args_schema=WorkerToolInput,
        ),
    ]
```

The `...` placeholders for `extract_*` functions in the snippet above are for brevity in the plan only — copy each function body verbatim from the existing file. Do not lose any logic.

Things deleted from the file: the `class ADPWorkerToolsComponent`, the `_execute_request` helper, the `version`/`changelog`/`inputs`/`outputs` class attributes, and imports of `ChangelogEntry`, `Component`, `HandleInput`, `Output`, `ClassVar`, `httpx` (no longer needed at module level after refactor).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/brycedeneen/dev/langflow && LFX_TEST_ALLOW_LANGFLOW=1 uv run --project src/lfx pytest src/lfx/tests/unit/components/adp/test_adp_worker_tools.py -v`

Expected: All tests pass (existing extract_* tests + new builder tests).

- [ ] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/adp/adp_worker_tools.py src/lfx/tests/unit/components/adp/test_adp_worker_tools.py
git commit -m "refactor(adp): convert worker tools to build_worker_tools(connection, cache)"
```

---

## Task 4: Refactor `adp_worker_demographic_tools.py` (canonical WRITE tile)

Pure-write tile (7 event POST tools, 0 reads). Establishes the pattern for all write-only tiles. The `request_cache` parameter is accepted but unused.

**Files:**
- Modify: `src/lfx/src/lfx/components/adp/adp_worker_demographic_tools.py`
- Modify: `src/lfx/tests/unit/components/adp/test_adp_worker_demographic_tools.py`

- [ ] **Step 1: Update tests first**

Replace component-instantiation paths in `test_adp_worker_demographic_tools.py` with direct `build_worker_demographic_tools(connection, RequestCache())` calls. The cache is irrelevant to writes; the test simply confirms tool count and POST body shapes against a mocked httpx client. Pattern mirrors Task 3's test rewrite.

Add at minimum one new test asserting cache is NOT consulted on writes:

```python
@pytest.mark.asyncio
async def test_writes_do_not_populate_cache():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_demographic_tools(conn, cache)

    response = MagicMock(spec=httpx.Response)
    response.status_code = 204
    response.text = ""

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    change_legal_name = next(t for t in tools if t.name == "change_legal_name")
    with patch("lfx.components.adp.adp_worker_demographic_tools.build_mtls_httpx_client", fake_client):
        await change_legal_name.ainvoke({"associate_oid": "G3ABC", "given_name": "Jane"})

    assert len(cache._entries) == 0
```

Replace component-test imports the same way as Task 3.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/brycedeneen/dev/langflow && LFX_TEST_ALLOW_LANGFLOW=1 uv run --project src/lfx pytest src/lfx/tests/unit/components/adp/test_adp_worker_demographic_tools.py -v`

Expected: ImportError on `build_worker_demographic_tools`.

- [ ] **Step 3: Refactor `adp_worker_demographic_tools.py`**

Apply the same pattern as Task 3:
1. Delete `class ADPWorkerDemographicToolsComponent` and its attributes (`display_name`, `name`, `icon`, `version`, `changelog`, `inputs`, `outputs`).
2. Delete imports of `ChangelogEntry`, `Component`, `HandleInput`, `Output`, `ClassVar`.
3. Move the body of `build_tools(self)` into a module-level `def build_worker_demographic_tools(connection: ADPConnection, request_cache: RequestCache) -> list[Tool]:`. The function signature accepts `request_cache` for registry uniformity even though writes don't use it.
4. Replace any `self.connection` references with the `connection` parameter.
5. Inline the previous `_execute_request` helper into the closure if it existed.

For pure-write tiles, no `cached_get_json` calls — keep `client.request(method="POST", ...)` direct.

Preserve all existing module-level constants (path templates, helper functions, Pydantic input schemas) verbatim.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/brycedeneen/dev/langflow && LFX_TEST_ALLOW_LANGFLOW=1 uv run --project src/lfx pytest src/lfx/tests/unit/components/adp/test_adp_worker_demographic_tools.py -v`

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/adp/adp_worker_demographic_tools.py src/lfx/tests/unit/components/adp/test_adp_worker_demographic_tools.py
git commit -m "refactor(adp): convert demographic tools to build_worker_demographic_tools"
```

---

## Task 5: Create `ADPToolsComponent` (initial registry: Worker + Demographic)

Build the unified component with just two tiles wired in. Tests prove the dispatcher works end-to-end before scaling to all 29 tiles.

**Files:**
- Create: `src/lfx/src/lfx/components/adp/adp_tools.py`
- Create: `src/lfx/tests/unit/components/adp/test_adp_tools.py`

- [ ] **Step 1: Write the failing tests**

Create `src/lfx/tests/unit/components/adp/test_adp_tools.py`:

```python
"""Tests for ADPToolsComponent — multi-select dispatcher over tile builders."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lfx.components.adp.adp_tools import TILE_BUILDERS, ADPToolsComponent


def _make_connection():
    conn = MagicMock()
    conn.access_token = "T1"
    conn.api_base_url = "https://api.adp.com"
    return conn


@pytest.mark.asyncio
async def test_no_selection_returns_empty_list():
    component = ADPToolsComponent()
    component.connection = _make_connection()
    component.tiles = []

    tools = await component.build_tools()

    assert tools == []
    assert "0 ADP tools" in component.status or "No tile" in component.status


@pytest.mark.asyncio
async def test_single_tile_dispatch_worker():
    component = ADPToolsComponent()
    component.connection = _make_connection()
    component.tiles = ["Worker"]

    tools = await component.build_tools()

    names = {t.name for t in tools}
    assert names == {
        "get_employee_name",
        "get_employee_addresses",
        "get_employee_contact_information",
        "get_employee_job",
        "get_employee_compensation",
        "get_employee_ids",
        "get_employee_dates",
        "get_employee_status",
        "get_employee_business_communication",
    }


@pytest.mark.asyncio
async def test_multiple_tile_dispatch_concatenates_in_order():
    component = ADPToolsComponent()
    component.connection = _make_connection()
    component.tiles = ["Worker", "Worker Demographic"]

    tools = await component.build_tools()

    # Worker (9) + Demographic (7) = 16 tools, no duplicates.
    assert len(tools) == 16
    assert len({t.name for t in tools}) == 16


@pytest.mark.asyncio
async def test_unknown_label_skipped_silently():
    component = ADPToolsComponent()
    component.connection = _make_connection()
    component.tiles = ["Worker", "GhostTile"]

    tools = await component.build_tools()

    # Worker only; GhostTile silently dropped.
    assert len(tools) == 9


def test_tile_labels_in_multiselect_options():
    options = next(i for i in ADPToolsComponent.inputs if i.name == "tiles").options
    for label in TILE_BUILDERS:
        assert label in options
    assert len(options) == len(TILE_BUILDERS)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/brycedeneen/dev/langflow && LFX_TEST_ALLOW_LANGFLOW=1 uv run --project src/lfx pytest src/lfx/tests/unit/components/adp/test_adp_tools.py -v`

Expected: ImportError on `adp_tools`.

- [ ] **Step 3: Create `adp_tools.py`**

```python
"""ADPToolsComponent — single multi-select component exposing ADP tile groups as agent tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from lfx.components.adp._shared import ADPConnection, RequestCache
from lfx.components.adp.adp_worker_demographic_tools import build_worker_demographic_tools
from lfx.components.adp.adp_worker_tools import build_worker_tools
from lfx.custom.custom_component.component import Component
from lfx.field_typing import Tool
from lfx.io import HandleInput, MultiselectInput, Output

TILE_BUILDERS: dict[str, Callable[[ADPConnection, RequestCache], list[Tool]]] = {
    "Worker": build_worker_tools,
    "Worker Demographic": build_worker_demographic_tools,
}


class ADPToolsComponent(Component):
    display_name = "ADP Tools"
    name = "ADPTools"
    description = (
        "Exposes ADP HR, payroll, time, and talent tools to a Langflow Agent. "
        "Pick which tile groups you want — each contributes 1-15 agent tools."
    )
    icon = "Users"
    version: int = 1
    documentation: str = "https://docs.langflow.org/component-adp-tools"

    inputs: ClassVar = [
        HandleInput(
            name="connection",
            display_name="ADP Connection",
            input_types=["ADPConnection"],
            info="Connection produced by an ADP Auth component.",
            required=True,
        ),
        MultiselectInput(
            name="tiles",
            display_name="Tools",
            options=list(TILE_BUILDERS.keys()),
            value=[],
            info=(
                "Select which ADP tool groups to expose to the agent. Each group "
                "adds 1-15 focused agent tools. Leaving this empty exposes nothing."
            ),
        ),
    ]

    outputs: ClassVar = [Output(display_name="Tools", name="tools", method="build_tools")]

    async def build_tools(self) -> list[Tool]:
        selected = list(getattr(self, "tiles", []) or [])
        if not selected:
            self.status = "No tile groups selected — agent will receive 0 ADP tools."
            return []
        cache = RequestCache(ttl_seconds=30, max_entries=128)
        tools: list[Tool] = []
        for label in selected:
            builder = TILE_BUILDERS.get(label)
            if builder is None:
                continue
            tools.extend(builder(self.connection, cache))
        self.status = f"Exposing {len(tools)} tool(s) from {len(selected)} tile group(s)."
        return tools
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/brycedeneen/dev/langflow && LFX_TEST_ALLOW_LANGFLOW=1 uv run --project src/lfx pytest src/lfx/tests/unit/components/adp/test_adp_tools.py -v`

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/adp/adp_tools.py src/lfx/tests/unit/components/adp/test_adp_tools.py
git commit -m "feat(adp): add ADPToolsComponent multi-select dispatcher"
```

---

## Task 6: End-to-end caching test

Prove the within-tile dedup works through `ADPToolsComponent`'s public surface. This is the user-visible payoff.

**Files:**
- Create: `src/lfx/tests/unit/components/adp/test_adp_tools_caching_e2e.py`

- [ ] **Step 1: Write the test**

```python
"""End-to-end caching test: 5 worker tools on same OID = 1 HTTP call."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lfx.components.adp.adp_tools import ADPToolsComponent

SAMPLE_WORKER_RESPONSE = {
    "workers": [
        {
            "associateOID": "G3ABC",
            "person": {
                "legalName": {"givenName": "Jane", "familyName1": "Doe"},
                "preferredName": {"givenName": "Janie", "familyName1": "Doe"},
                "communication": {"emails": [], "landlines": [], "mobiles": []},
            },
            "workAssignments": [],
            "workerStatus": {},
        },
    ],
}


def _make_connection():
    conn = MagicMock()
    conn.access_token = "T1"
    conn.api_base_url = "https://api.adp.com"
    return conn


@pytest.mark.asyncio
async def test_five_worker_tools_same_oid_one_http_call():
    component = ADPToolsComponent()
    component.connection = _make_connection()
    component.tiles = ["Worker"]

    tools = await component.build_tools()
    by_name = {t.name: t for t in tools}

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = SAMPLE_WORKER_RESPONSE

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_worker_tools.build_mtls_httpx_client", fake_client):
        await by_name["get_employee_name"].ainvoke({"associate_oid": "G3ABC"})
        await by_name["get_employee_addresses"].ainvoke({"associate_oid": "G3ABC"})
        await by_name["get_employee_contact_information"].ainvoke({"associate_oid": "G3ABC"})
        await by_name["get_employee_job"].ainvoke({"associate_oid": "G3ABC"})
        await by_name["get_employee_compensation"].ainvoke({"associate_oid": "G3ABC"})

    assert client.request.await_count == 1


@pytest.mark.asyncio
async def test_two_oids_two_http_calls():
    component = ADPToolsComponent()
    component.connection = _make_connection()
    component.tiles = ["Worker"]

    tools = await component.build_tools()
    by_name = {t.name: t for t in tools}

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = SAMPLE_WORKER_RESPONSE

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_worker_tools.build_mtls_httpx_client", fake_client):
        await by_name["get_employee_name"].ainvoke({"associate_oid": "G3ABC"})
        await by_name["get_employee_compensation"].ainvoke({"associate_oid": "G3ABC"})
        await by_name["get_employee_name"].ainvoke({"associate_oid": "G3XYZ"})
        await by_name["get_employee_compensation"].ainvoke({"associate_oid": "G3XYZ"})

    assert client.request.await_count == 2
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd /Users/brycedeneen/dev/langflow && LFX_TEST_ALLOW_LANGFLOW=1 uv run --project src/lfx pytest src/lfx/tests/unit/components/adp/test_adp_tools_caching_e2e.py -v`

Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add src/lfx/tests/unit/components/adp/test_adp_tools_caching_e2e.py
git commit -m "test(adp): add E2E caching test proving within-tile dedup"
```

---

## Task 7: Refactor remaining 27 tile files

Apply the canonical pattern from Tasks 3 (read tiles) or 4 (write tiles) to each of the remaining 27 tiles. The pattern is the same; only the tile-specific function/class names and helpers differ.

**Pattern reminder (do this for each tile):**

1. Open `adp_<tile>_tools.py` and `tests/.../test_adp_<tile>_tools.py`.
2. Identify whether the tile is **READ** (has GETs to `/hr/v2/...` or `/payroll/...` etc.), **WRITE** (only POSTs to `/events/hr/v1/...`), or **MIXED**.
3. **For READ tiles:** wire reads through `cached_get_json` (per Task 3 pattern). Convert any per-tile `_fetch_*` helper from a method to a module function with `*, request_cache: RequestCache` keyword arg. Use `cached_get_json` inside it.
4. **For WRITE tiles:** keep `client.request("POST", ...)` direct (no cache); accept `request_cache` in the builder signature anyway for registry uniformity.
5. Delete the `Component` subclass (and its `display_name`, `name`, `icon`, `version`, `changelog`, `inputs`, `outputs` attributes).
6. Delete unused imports (`Component`, `HandleInput`, `Output`, `ChangelogEntry`, `ClassVar`).
7. Promote `build_tools(self)` to module-level `build_<tile>_tools(connection: ADPConnection, request_cache: RequestCache) -> list[Tool]`. Replace `self.connection` with `connection`.
8. Update the corresponding test file to:
   - Import `build_<tile>_tools` instead of `ADP<Tile>ToolsComponent`.
   - Call `build_<tile>_tools(fake_connection, RequestCache())` instead of instantiating the component class.
   - Patch `lfx.components.adp.adp_<tile>_tools.build_mtls_httpx_client` (and `fetch_token` if 401-refresh is tested) at the new module path. Existing per-tool behavior assertions stay verbatim.
9. Run the test file in isolation; expect green.
10. Tick the checkbox.

**Per-tile work list** (check off as you go):

- [ ] `adp_applicant_onboarding_tools.py` — MIXED (1 read + 1 write per heuristic). `build_applicant_onboarding_tools`.
- [ ] `adp_benefits_tools.py` — MIXED. `build_benefits_tools`.
- [ ] `adp_data_collection_entries_tools.py` — MIXED. `build_data_collection_entries_tools`.
- [ ] `adp_deduction_configurations_tools.py` — READ (no `/events/`). `build_deduction_configurations_tools`.
- [ ] `adp_job_applicants_tools.py` — MIXED (high read count). `build_job_applicants_tools`.
- [ ] `adp_job_requisitions_tools.py` — READ. `build_job_requisitions_tools`.
- [ ] `adp_pay_data_input_tools.py` — MIXED (high read count). `build_pay_data_input_tools`.
- [ ] `adp_pay_distributions_tools.py` — MIXED. `build_pay_distributions_tools`.
- [ ] `adp_pay_statements_tools.py` — READ. `build_pay_statements_tools`.
- [ ] `adp_talent_tools.py` — MIXED. `build_talent_tools`.
- [ ] `adp_team_time_cards_tools.py` — READ. `build_team_time_cards_tools`.
- [ ] `adp_time_cards_tools.py` — READ. `build_time_cards_tools`.
- [ ] `adp_time_off_tools.py` — MIXED. `build_time_off_tools`.
- [ ] `adp_us_tax_profiles_tools.py` — MIXED. `build_us_tax_profiles_tools`.
- [ ] `adp_work_schedules_tools.py` — MIXED. `build_work_schedules_tools`.
- [ ] `adp_worker_assignment_tools.py` — WRITE-heavy (4 events). `build_worker_assignment_tools`.
- [ ] `adp_worker_assignment_v3_tools.py` — READ. `build_worker_assignment_v3_tools`.
- [ ] `adp_worker_biological_tools.py` — verify class. `build_worker_biological_tools`.
- [ ] `adp_worker_business_communication_tools.py` — MIXED. `build_worker_business_communication_tools`.
- [ ] `adp_worker_compensation_tools.py` — WRITE. `build_worker_compensation_tools`.
- [ ] `adp_worker_deployment_tools.py` — verify class. `build_worker_deployment_tools`.
- [ ] `adp_worker_hr_profiles_tools.py` — MIXED (many reads + 2 writes). `build_worker_hr_profiles_tools`.
- [ ] `adp_worker_identification_tools.py` — MIXED (mostly write). `build_worker_identification_tools`.
- [ ] `adp_worker_leaves_tools.py` — MIXED (many reads + many writes). `build_worker_leaves_tools`.
- [ ] `adp_worker_lifecycle_tools.py` — MIXED. `build_worker_lifecycle_tools`.
- [ ] `adp_worker_payroll_instructions_tools.py` — MIXED. `build_worker_payroll_instructions_tools`.
- [ ] `adp_worker_personal_communication_tools.py` — WRITE-heavy. `build_worker_personal_communication_tools`.

**Verification after each tile:** `cd /Users/brycedeneen/dev/langflow && LFX_TEST_ALLOW_LANGFLOW=1 uv run --project src/lfx pytest src/lfx/tests/unit/components/adp/test_adp_<tile>_tools.py -v`

**Commit cadence:** Group related tiles per commit so review stays manageable. Suggested 4 commits:

- [ ] **Commit A: Worker family** — `adp_worker_assignment_tools.py`, `adp_worker_assignment_v3_tools.py`, `adp_worker_biological_tools.py`, `adp_worker_business_communication_tools.py`, `adp_worker_compensation_tools.py`, `adp_worker_deployment_tools.py`, `adp_worker_hr_profiles_tools.py`, `adp_worker_identification_tools.py`, `adp_worker_leaves_tools.py`, `adp_worker_lifecycle_tools.py`, `adp_worker_payroll_instructions_tools.py`, `adp_worker_personal_communication_tools.py`.

```bash
git add src/lfx/src/lfx/components/adp/adp_worker_assignment_tools.py \
  src/lfx/src/lfx/components/adp/adp_worker_assignment_v3_tools.py \
  src/lfx/src/lfx/components/adp/adp_worker_biological_tools.py \
  src/lfx/src/lfx/components/adp/adp_worker_business_communication_tools.py \
  src/lfx/src/lfx/components/adp/adp_worker_compensation_tools.py \
  src/lfx/src/lfx/components/adp/adp_worker_deployment_tools.py \
  src/lfx/src/lfx/components/adp/adp_worker_hr_profiles_tools.py \
  src/lfx/src/lfx/components/adp/adp_worker_identification_tools.py \
  src/lfx/src/lfx/components/adp/adp_worker_leaves_tools.py \
  src/lfx/src/lfx/components/adp/adp_worker_lifecycle_tools.py \
  src/lfx/src/lfx/components/adp/adp_worker_payroll_instructions_tools.py \
  src/lfx/src/lfx/components/adp/adp_worker_personal_communication_tools.py \
  src/lfx/tests/unit/components/adp/test_adp_worker_assignment_tools.py \
  src/lfx/tests/unit/components/adp/test_adp_worker_assignment_v3_tools.py \
  src/lfx/tests/unit/components/adp/test_adp_worker_biological_tools.py \
  src/lfx/tests/unit/components/adp/test_adp_worker_business_communication_tools.py \
  src/lfx/tests/unit/components/adp/test_adp_worker_compensation_tools.py \
  src/lfx/tests/unit/components/adp/test_adp_worker_deployment_tools.py \
  src/lfx/tests/unit/components/adp/test_adp_worker_hr_profiles_tools.py \
  src/lfx/tests/unit/components/adp/test_adp_worker_identification_tools.py \
  src/lfx/tests/unit/components/adp/test_adp_worker_leaves_tools.py \
  src/lfx/tests/unit/components/adp/test_adp_worker_lifecycle_tools.py \
  src/lfx/tests/unit/components/adp/test_adp_worker_payroll_instructions_tools.py \
  src/lfx/tests/unit/components/adp/test_adp_worker_personal_communication_tools.py
git commit -m "refactor(adp): convert worker family tiles to module-level builders"
```

If a test file does not exist for any of the listed tiles (verify with `ls src/lfx/tests/unit/components/adp/`), drop it from the `git add` list rather than failing the command.

- [ ] **Commit B: Pay & Tax** — `adp_pay_data_input_tools.py`, `adp_pay_distributions_tools.py`, `adp_pay_statements_tools.py`, `adp_us_tax_profiles_tools.py`, `adp_deduction_configurations_tools.py` + their test files. Same `git add … && git commit -m "refactor(adp): convert pay & tax tiles to module-level builders"`.

- [ ] **Commit C: Time** — `adp_time_cards_tools.py`, `adp_team_time_cards_tools.py`, `adp_time_off_tools.py`, `adp_work_schedules_tools.py` + their test files. Commit message: `refactor(adp): convert time tiles to module-level builders`.

- [ ] **Commit D: Talent, Recruiting, Other** — `adp_talent_tools.py`, `adp_job_applicants_tools.py`, `adp_job_requisitions_tools.py`, `adp_applicant_onboarding_tools.py`, `adp_benefits_tools.py`, `adp_data_collection_entries_tools.py` + their test files. Commit message: `refactor(adp): convert talent, recruiting, and other tiles to module-level builders`.

- [ ] **Step F: Run the full ADP tile test suite to confirm no regressions**

Run: `cd /Users/brycedeneen/dev/langflow && LFX_TEST_ALLOW_LANGFLOW=1 uv run --project src/lfx pytest src/lfx/tests/unit/components/adp/ -v --ignore=src/lfx/tests/unit/components/adp/test_bundle_init.py --ignore=src/lfx/tests/unit/components/adp/test_adp_bundle_smoke.py`

Expected: All tile tests pass. (Bundle tests still expect old class exports — those get fixed in Task 8.)

---

## Task 8: Expand `TILE_BUILDERS`, rewrite `__init__.py`, update bundle tests

Now that all 29 tile files expose module-level builders, wire them all into the registry, drop deprecated component exports from the package init, and fix the bundle smoke tests.

**Files:**
- Modify: `src/lfx/src/lfx/components/adp/adp_tools.py` (expand `TILE_BUILDERS` to 29 entries)
- Modify: `src/lfx/src/lfx/components/adp/__init__.py` (drop 29 component exports, add `ADPToolsComponent`)
- Modify: `src/lfx/tests/unit/components/adp/test_bundle_init.py` (rewrite expected exports)
- Modify: `src/lfx/tests/unit/components/adp/test_adp_tools.py` (add full-coverage drift test)

- [ ] **Step 1: Expand `TILE_BUILDERS`**

In `src/lfx/src/lfx/components/adp/adp_tools.py`, replace the imports section and `TILE_BUILDERS` dict with the full 29-tile registry. Use the exact label-to-builder mapping from the spec:

```python
from lfx.components.adp._shared import ADPConnection, RequestCache
from lfx.components.adp.adp_applicant_onboarding_tools import build_applicant_onboarding_tools
from lfx.components.adp.adp_benefits_tools import build_benefits_tools
from lfx.components.adp.adp_data_collection_entries_tools import build_data_collection_entries_tools
from lfx.components.adp.adp_deduction_configurations_tools import build_deduction_configurations_tools
from lfx.components.adp.adp_job_applicants_tools import build_job_applicants_tools
from lfx.components.adp.adp_job_requisitions_tools import build_job_requisitions_tools
from lfx.components.adp.adp_pay_data_input_tools import build_pay_data_input_tools
from lfx.components.adp.adp_pay_distributions_tools import build_pay_distributions_tools
from lfx.components.adp.adp_pay_statements_tools import build_pay_statements_tools
from lfx.components.adp.adp_talent_tools import build_talent_tools
from lfx.components.adp.adp_team_time_cards_tools import build_team_time_cards_tools
from lfx.components.adp.adp_time_cards_tools import build_time_cards_tools
from lfx.components.adp.adp_time_off_tools import build_time_off_tools
from lfx.components.adp.adp_us_tax_profiles_tools import build_us_tax_profiles_tools
from lfx.components.adp.adp_work_schedules_tools import build_work_schedules_tools
from lfx.components.adp.adp_worker_assignment_tools import build_worker_assignment_tools
from lfx.components.adp.adp_worker_assignment_v3_tools import build_worker_assignment_v3_tools
from lfx.components.adp.adp_worker_biological_tools import build_worker_biological_tools
from lfx.components.adp.adp_worker_business_communication_tools import build_worker_business_communication_tools
from lfx.components.adp.adp_worker_compensation_tools import build_worker_compensation_tools
from lfx.components.adp.adp_worker_demographic_tools import build_worker_demographic_tools
from lfx.components.adp.adp_worker_deployment_tools import build_worker_deployment_tools
from lfx.components.adp.adp_worker_hr_profiles_tools import build_worker_hr_profiles_tools
from lfx.components.adp.adp_worker_identification_tools import build_worker_identification_tools
from lfx.components.adp.adp_worker_leaves_tools import build_worker_leaves_tools
from lfx.components.adp.adp_worker_lifecycle_tools import build_worker_lifecycle_tools
from lfx.components.adp.adp_worker_payroll_instructions_tools import build_worker_payroll_instructions_tools
from lfx.components.adp.adp_worker_personal_communication_tools import build_worker_personal_communication_tools
from lfx.components.adp.adp_worker_tools import build_worker_tools

TILE_BUILDERS: dict[str, Callable[[ADPConnection, RequestCache], list[Tool]]] = {
    "Worker": build_worker_tools,
    "Worker Assignment": build_worker_assignment_tools,
    "Worker Assignment v3": build_worker_assignment_v3_tools,
    "Worker HR Profiles": build_worker_hr_profiles_tools,
    "Worker Lifecycle": build_worker_lifecycle_tools,
    "Worker Identification": build_worker_identification_tools,
    "Worker Biological": build_worker_biological_tools,
    "Worker Deployment": build_worker_deployment_tools,
    "Worker Leaves": build_worker_leaves_tools,
    "Worker Payroll Instructions": build_worker_payroll_instructions_tools,
    "Worker Personal Communication": build_worker_personal_communication_tools,
    "Worker Business Communication": build_worker_business_communication_tools,
    "Worker Compensation": build_worker_compensation_tools,
    "Worker Demographic": build_worker_demographic_tools,
    "Pay Data Input": build_pay_data_input_tools,
    "Pay Distributions": build_pay_distributions_tools,
    "Pay Statements": build_pay_statements_tools,
    "US Tax Profiles": build_us_tax_profiles_tools,
    "Deduction Configurations": build_deduction_configurations_tools,
    "Time Cards": build_time_cards_tools,
    "Team Time Cards": build_team_time_cards_tools,
    "Time Off": build_time_off_tools,
    "Work Schedules": build_work_schedules_tools,
    "Talent": build_talent_tools,
    "Job Applicants": build_job_applicants_tools,
    "Job Requisitions": build_job_requisitions_tools,
    "Applicant Onboarding": build_applicant_onboarding_tools,
    "Benefits": build_benefits_tools,
    "Data Collection Entries": build_data_collection_entries_tools,
}
```

- [ ] **Step 2: Add the 29-tile drift test**

Append to `src/lfx/tests/unit/components/adp/test_adp_tools.py`:

```python
def test_registry_covers_all_29_tiles():
    assert len(TILE_BUILDERS) == 29
    options = next(i for i in ADPToolsComponent.inputs if i.name == "tiles").options
    assert set(options) == set(TILE_BUILDERS.keys())
    assert len(options) == 29
```

- [ ] **Step 3: Rewrite `__init__.py`**

Replace `src/lfx/src/lfx/components/adp/__init__.py` with:

```python
"""ADP connector bundle: Auth, API Request, MCP, Trigger, and unified Tools component."""

from .adp_api_request import ADPAPIRequestComponent
from .adp_auth import ADPAuthComponent
from .adp_mcp import ADPMCPComponent
from .adp_tools import ADPToolsComponent
from .adp_trigger import ADPTriggerComponent

__all__ = [
    "ADPAPIRequestComponent",
    "ADPAuthComponent",
    "ADPMCPComponent",
    "ADPToolsComponent",
    "ADPTriggerComponent",
]
```

- [ ] **Step 4: Rewrite `test_bundle_init.py`**

Replace its expected-exports list with the new bundle:

```python
def test_bundle_exports_all_components():
    from lfx.components.adp import (
        ADPAPIRequestComponent,
        ADPAuthComponent,
        ADPMCPComponent,
        ADPToolsComponent,
        ADPTriggerComponent,
    )

    assert ADPAuthComponent.name == "ADPAuth"
    assert ADPToolsComponent.name == "ADPTools"
    assert ADPTriggerComponent.name == "ADPTrigger"
    assert ADPMCPComponent.name == "ADPMCP"
    assert ADPAPIRequestComponent.name == "ADPAPIRequest"


def test_bundle_all_lists_only_kept_components():
    from lfx.components.adp import __all__ as exports

    assert set(exports) == {
        "ADPAPIRequestComponent",
        "ADPAuthComponent",
        "ADPMCPComponent",
        "ADPToolsComponent",
        "ADPTriggerComponent",
    }
```

If the existing file has additional assertions about specific component classes that are now deleted (e.g. `assert ADPJobApplicantsToolsComponent.name == "ADPJobApplicantsTools"`), delete those assertions.

- [ ] **Step 5: Update `test_adp_bundle_smoke.py` if needed**

Open `src/lfx/tests/unit/components/adp/test_adp_bundle_smoke.py`. It already imports from `__all__`, so most assertions auto-adapt. Look for any hard-coded reference to the deleted class names (`ADPWorkerToolsComponent`, etc.) and either delete or rewrite to use `ADPToolsComponent`. If the file asserts a specific bundle size, update the expected count to 5 (Auth, Trigger, MCP, APIRequest, Tools).

- [ ] **Step 6: Run the full ADP test suite**

Run: `cd /Users/brycedeneen/dev/langflow && LFX_TEST_ALLOW_LANGFLOW=1 uv run --project src/lfx pytest src/lfx/tests/unit/components/adp/ -v`

Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/lfx/src/lfx/components/adp/adp_tools.py \
  src/lfx/src/lfx/components/adp/__init__.py \
  src/lfx/tests/unit/components/adp/test_adp_tools.py \
  src/lfx/tests/unit/components/adp/test_bundle_init.py \
  src/lfx/tests/unit/components/adp/test_adp_bundle_smoke.py
git commit -m "feat(adp): wire 29-tile registry and drop deprecated component exports"
```

---

## Task 9: Clean stale agent metadata and regenerate component_index

The agent-assist YAML files reference deleted class names. Strip those entries and add a stub for `ADPToolsComponent` (the bootstrap script will fill in details on its next run, per spec). Also regenerate the static component index that powers the picker.

**Files:**
- Modify: `src/backend/base/langflow/services/component_assist/agent_metadata/adp.yaml`
- Modify: `src/backend/base/langflow/services/component_assist/guides/adp.yaml`
- Modify: `src/lfx/src/lfx/_assets/component_index.json` (regenerated, not hand-edited)

- [ ] **Step 1: Inventory stale references**

Run a defensive grep to confirm where deleted class names are referenced beyond the YAMLs and `component_index.json`:

```
grep -rln "ADPWorkerToolsComponent\|ADPPayDataInputToolsComponent\|ADPTimeOffToolsComponent" \
  src/lfx src/backend/base /Users/brycedeneen/dev/langflow/scripts 2>/dev/null \
  | grep -v __pycache__ | grep -v node_modules | grep -v .worktrees | grep -v frontend/build
```

Expected hits: only the YAML files and `component_index.json` listed in this task. If any source file or starter project references the deleted class names, add it to this task's modify list before continuing.

Then enumerate the stale YAML entries:

`grep -E "^- component_name:|^  - name:" src/backend/base/langflow/services/component_assist/agent_metadata/adp.yaml | head -40`

This shows every component-keyed entry. Anything that names one of the 29 deleted classes (`ADP<X>ToolsComponent` where `<X>` is not `Tools`) must be removed.

- [ ] **Step 2: Edit `agent_metadata/adp.yaml`**

Remove every YAML block whose `component_name` is one of the 29 deleted classes:

```
ADPApplicantOnboardingToolsComponent
ADPBenefitsToolsComponent
ADPDataCollectionEntriesToolsComponent
ADPDeductionConfigurationsToolsComponent
ADPJobApplicantsToolsComponent
ADPJobRequisitionsToolsComponent
ADPPayDataInputToolsComponent
ADPPayDistributionsToolsComponent
ADPPayStatementsToolsComponent
ADPTalentToolsComponent
ADPTeamTimeCardsToolsComponent
ADPTimeCardsToolsComponent
ADPTimeOffToolsComponent
ADPUSTaxProfilesToolsComponent
ADPWorkSchedulesToolsComponent
ADPWorkerAssignmentToolsComponent
ADPWorkerAssignmentV3ToolsComponent
ADPWorkerBiologicalToolsComponent
ADPWorkerBusinessCommunicationToolsComponent
ADPWorkerCompensationToolsComponent
ADPWorkerDemographicToolsComponent
ADPWorkerDeploymentToolsComponent
ADPWorkerHrProfilesToolsComponent
ADPWorkerIdentificationToolsComponent
ADPWorkerLeavesToolsComponent
ADPWorkerLifecycleToolsComponent
ADPWorkerPayrollInstructionsToolsComponent
ADPWorkerPersonalCommunicationToolsComponent
ADPWorkerToolsComponent
```

Keep entries for the 4 surviving non-tile components if they exist: `ADPAuthComponent`, `ADPTriggerComponent`, `ADPMCPComponent`, `ADPAPIRequestComponent`.

Append a stub for the new component:

```yaml
- component_name: ADPToolsComponent
  agent_summary: |-
    You help the user expose ADP HR, payroll, time, and talent agent tools through a single component. The user picks tile groups via a multi-select; each group adds its existing focused agent tools (worker reads, event mutations, etc.) to the agent. Prefer over the deprecated per-tile components because it consolidates ADP coverage into one node and enables per-build read-cache reuse across tools.
  agent_usage_notes: |-
    ## What it does
    Provides a multi-select over ADP tile groups (Worker, Pay Data Input, Time Off, …). Each selected group contributes 1-15 focused agent tools to the output `tools` list, all sharing a single `ADPConnection` and a shared per-build read cache that deduplicates GETs to the same ADP resource.

    ## Inputs to ask about
    - **connection** - Ask the user to wire the output of an ADP Auth component here; required before any tool can authenticate.
    - **tiles** - Ask the user which ADP tile groups they want exposed. Suggest the smallest set that covers the use case; each tile adds 1-15 tools to the agent.

    ## Outputs
    - **tools** - A list of `StructuredTool` instances the user can wire into a Langflow Agent component.

    ## Notes
    - Empty selection produces an empty tool list — the agent receives 0 ADP tools.
    - Read tools share a 30-second cache scoped to one component build, so multiple tools on the same employee within a turn make a single API call.
    - Mutating tools (event POSTs) bypass the cache entirely.
```

- [ ] **Step 3: Edit `guides/adp.yaml` similarly**

Apply the same delete-stale-keep-survivors pattern. If the file has narrative guides keyed by component_name, drop guides for the 29 deleted classes. The bootstrap script regenerates content on its next run; an empty body for `ADPToolsComponent` is acceptable for now.

- [ ] **Step 4: Regenerate `component_index.json`**

Run: `cd /Users/brycedeneen/dev/langflow && uv run --project src/lfx python scripts/build_component_index.py`

Expected: The script writes a new `src/lfx/src/lfx/_assets/component_index.json`. Inspect with `git diff --stat src/lfx/src/lfx/_assets/component_index.json` — should show a meaningful churn (29 entries removed, 1 added).

If the script does not exist at that exact path, run `find /Users/brycedeneen/dev/langflow/scripts -name "build_component_index.py"` to locate it.

- [ ] **Step 5: Run the component-index drift test**

Run: `cd /Users/brycedeneen/dev/langflow && LFX_TEST_ALLOW_LANGFLOW=1 uv run --project src/lfx pytest src/lfx/tests/unit/test_component_index.py -v`

Expected: All tests pass. If the test file asserts that the regenerated index matches the source, this confirms the regen step worked.

- [ ] **Step 6: Commit**

```bash
git add src/backend/base/langflow/services/component_assist/agent_metadata/adp.yaml \
  src/backend/base/langflow/services/component_assist/guides/adp.yaml \
  src/lfx/src/lfx/_assets/component_index.json
git commit -m "chore(adp): drop stale agent metadata and regenerate component index"
```

---

## Task 10: Final verification

Run the full ADP suite, the bundle smoke test, and the broader lfx test suite to confirm nothing else broke. Frontend smoke is optional but recommended — load Langflow, drag the new "ADP Tools" component into a flow, confirm the multi-select renders.

- [ ] **Step 1: Full ADP test suite**

Run: `cd /Users/brycedeneen/dev/langflow && LFX_TEST_ALLOW_LANGFLOW=1 uv run --project src/lfx pytest src/lfx/tests/unit/components/adp/ -v`

Expected: All tests pass.

- [ ] **Step 2: Full lfx test suite**

Run: `cd /Users/brycedeneen/dev/langflow && LFX_TEST_ALLOW_LANGFLOW=1 uv run --project src/lfx pytest src/lfx/tests/ -x`

Expected: All tests pass. If a test outside `tests/unit/components/adp/` fails, investigate — it likely references the deleted classes via `lfx.components.adp.*`. Grep for the failing class name and update.

- [ ] **Step 3: Component-index drift test (sanity)**

Run: `cd /Users/brycedeneen/dev/langflow && LFX_TEST_ALLOW_LANGFLOW=1 uv run --project src/lfx pytest src/lfx/tests/unit/test_component_index.py -v`

Expected: Pass.

- [ ] **Step 4 (optional): Frontend smoke**

Start Langflow locally; in the component sidebar, search for "ADP". You should see exactly 5 ADP components: ADP Auth, ADP API Request, ADP MCP, ADP Trigger, ADP Tools. Drag "ADP Tools" onto the canvas. Confirm:

- The "Tools" multi-select input appears with all 29 tile labels.
- Selecting `["Worker"]` and clicking Build produces no errors.
- The component output handle is labeled "Tools" and has type `Tool`.

If the dev server isn't running, see `make backend` / `make frontend` per the repo Makefile. Skip this step in a CI / agent context.

- [ ] **Step 5: Self-review the diff**

Run: `git log --oneline platform-multi-tenant..HEAD`

Expected: Roughly 9 focused commits (RequestCache, cached_get_json, Worker, Demographic, ADPToolsComponent, E2E test, 4 tile family commits, registry expansion, metadata cleanup).

Run: `git diff platform-multi-tenant..HEAD --stat | tail -5`

Expected: One new file `adp_tools.py` (~80 LOC), 29 modified tile files (each smaller than before), updated `_shared.py`, updated `__init__.py`, two new test files (`test_request_cache.py`, `test_adp_tools.py`, `test_adp_tools_caching_e2e.py`), regenerated `component_index.json`, cleaned metadata YAMLs.

Plan execution complete.

---

## Self-Review Notes

Items the executor should keep an eye on:

1. **Per-tile heuristic classification in Task 7 was based on simple grep counts** (`/events/hr/` for writes, `.get(` for reads). Two false positives are possible: a `.get(` in JSON-payload construction is not a real read, and an `/events/` path constant string in a comment is not a real write. When in doubt, scan the tile's source for actual `client.request` calls — those are the ground truth.

2. **The `cached_get_json` 401-refresh contract.** The helper itself does NOT retry on 401; the per-tile `_fetch_*` wrapper does. This keeps token-refresh logic out of the cache layer (where it doesn't belong) and lets each tile control its own retry semantics. Task 3's `_fetch_worker` shows the canonical 401-handling shape; replicate it in any read tile that handles 401-refresh.

3. **The `cached_get_json` implementation in Task 2 reaches into `cache._entries` directly to skip caching errors.** That's a tight coupling but acceptable because both live in `_shared.py`. If a future refactor splits them, expose a `cache.peek(key)` and `cache.put(key, value)` API.

4. **`test_bundle_init.py` may have additional assertions I haven't seen.** Step 4 of Task 8 says to delete assertions referencing deleted classes — when reading the actual file, expect more assertions than just `name` checks (for example, `assert hasattr(component, "build_tools")`-style checks). Delete or rewrite those to target `ADPToolsComponent` instead.

5. **Frontend cache.** Langflow's frontend may cache component metadata. After the rebuild, hard-refresh the browser if the new "ADP Tools" component doesn't appear or the old ones still show.

---

**Execution options:**

1. **Subagent-Driven (recommended)** — Dispatch a fresh subagent per task. Each subagent reads the spec + this plan, executes its task, the parent reviews between tasks. Best for this plan because Task 7's 27 tile refactors benefit from isolated, mechanical work in fresh contexts.

2. **Inline Execution** — Run all tasks in this session using `superpowers:executing-plans`. Faster but holds more context in one window; risk of cache pollution between mechanical tile refactors.

Which approach?

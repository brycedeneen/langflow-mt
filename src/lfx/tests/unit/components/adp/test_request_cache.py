"""Tests for RequestCache and cached_get_json."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache, cached_get_json


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
    now_ref = [1000.0]

    def fake_monotonic():
        return now_ref[0]

    with patch("lfx.components.adp._shared.time.monotonic", side_effect=fake_monotonic):
        first = await cache.get_or_fetch(key, fetch)
        now_ref[0] = 1031.0  # advance past 30s TTL
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

    # Re-fetching "A" calls fetch_a_again because A was evicted
    calls = 0

    async def fetch_a_again():
        nonlocal calls
        calls += 1
        return "a-fresh"

    result = await cache.get_or_fetch("A", fetch_a_again)
    assert result == "a-fresh"
    assert calls == 1
    # B is the LRU when A is re-inserted (C was more recently accessed), so B is evicted.
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


@pytest.mark.asyncio
async def test_cached_get_json_concurrent_cold_miss_fires_one_request():
    """Regression guard: parallel cold-miss callers must not all fire HTTP requests."""
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    response_payload = {"workers": [{"associateOID": "G3ABC"}]}

    in_flight = 0
    max_in_flight = 0

    async def _request(*_args, **_kwargs):
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_payload
        return mock_response

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.side_effect = _request

    url = "https://api.adp.com/hr/v2/workers/G3ABC"
    headers = {"Authorization": "Bearer T1"}

    results = await asyncio.gather(*[
        cached_get_json(client=client, cache=cache, url=url, headers=headers)
        for _ in range(10)
    ])

    assert all(r == response_payload for r in results)
    assert max_in_flight == 1
    assert client.request.await_count == 1


@pytest.mark.asyncio
async def test_cached_get_json_returns_text_when_error_body_is_not_json():
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    error_response = MagicMock(spec=httpx.Response)
    error_response.status_code = 502
    error_response.json.side_effect = ValueError("not json")
    error_response.text = "<html>Bad Gateway</html>"

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = error_response

    result = await cached_get_json(
        client=client,
        cache=cache,
        url="https://api.adp.com/hr/v2/workers/G3ABC",
        headers={"Authorization": "Bearer T1"},
    )

    assert result == {"error": "<html>Bad Gateway</html>", "status_code": 502}

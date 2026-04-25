"""ADP data-collection-entries tools — module-level builder.

Tile has one POST `data-collection-entries.process` event + one GET for the
event result by event-id. Exposes two tools: `process_data_collection_entries`
(gated) and `get_data_collection_event_result` (read).
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from lfx.components.adp._shared import (
    HTTP_CLIENT_ERROR_MIN,
    HTTP_UNAUTHORIZED,
    ADPConnection,
    RequestCache,
    build_mtls_httpx_client,
    cached_get_json,
    fetch_token,
    validate_adp_url,
)
from lfx.field_typing import Tool  # noqa: TC001 — runtime return annotation used by LangFlow registry

PATH_PROCESS = "/events/time/v1/data-collection-entries.process"
PATH_RESULT = "/events/time/v1/data-collection-entries.process/{event_id}"


class ProcessDataCollectionEntriesInput(BaseModel):
    event_body: dict[str, Any] = Field(
        description=(
            "Full ADP event body: the `{events: [{data: {eventContext, transform: {...}}}]}` "
            "envelope. Pass through ADP-shaped data unchanged."
        ),
    )


class GetDataCollectionEventResultInput(BaseModel):
    event_id: str = Field(description="Event ID returned from the .process POST.")


async def _fetch_event_result(
    conn: ADPConnection,
    *,
    event_id: str,
    request_cache: RequestCache,
) -> dict[str, Any]:
    path = PATH_RESULT.format(event_id=event_id)
    url = f"{conn.api_base_url}{path}"
    validate_adp_url(url, field_name="api_base_url")
    key = RequestCache.make_key("GET", url, None)

    # Peek before opening the mTLS client so cache hits skip PEM-file churn.
    cached = request_cache.peek(key)
    if cached is not None:
        return cached

    async with build_mtls_httpx_client(conn, timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {conn.access_token}"}
        result = await cached_get_json(client=client, cache=request_cache, url=url, headers=headers)
        if result.get("status_code") == HTTP_UNAUTHORIZED:
            await fetch_token(conn, force=True)
            headers["Authorization"] = f"Bearer {conn.access_token}"
            result = await cached_get_json(client=client, cache=request_cache, url=url, headers=headers)

    return result


async def _post_event(conn: ADPConnection, *, path: str, body: dict[str, Any]) -> dict[str, Any]:
    """POST a single ADP event, with one 401-refresh retry."""
    url = f"{conn.api_base_url}{path}"
    validate_adp_url(url, field_name="api_base_url")
    headers = {"Authorization": f"Bearer {conn.access_token}"}
    async with build_mtls_httpx_client(conn, timeout=30.0) as client:
        response = await client.request("POST", url=url, headers=headers, json=body, timeout=30.0)
        if response.status_code == HTTP_UNAUTHORIZED:
            await fetch_token(conn, force=True)
            headers["Authorization"] = f"Bearer {conn.access_token}"
            response = await client.request("POST", url=url, headers=headers, json=body, timeout=30.0)
    if response.status_code >= HTTP_CLIENT_ERROR_MIN:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        return {"error": detail, "status_code": response.status_code}
    try:
        return response.json()
    except ValueError:
        return {"ok": True, "status_code": response.status_code}


def build_data_collection_entries_tools(
    connection: ADPConnection,
    request_cache: RequestCache,
    *,
    enable_mutations: bool = False,
) -> list[Tool]:
    conn = connection

    async def _get_data_collection_event_result(event_id: str) -> dict[str, Any]:
        return await _fetch_event_result(conn, event_id=event_id, request_cache=request_cache)

    tools: list[Tool] = [
        StructuredTool.from_function(
            name="get_data_collection_event_result",
            description=(
                "Get the result/status of a prior data-collection-entries.process event "
                "by its event ID."
            ),
            coroutine=_get_data_collection_event_result,
            args_schema=GetDataCollectionEventResultInput,
        ),
    ]

    if not enable_mutations:
        return tools

    async def _process_data_collection_entries(event_body: dict[str, Any]) -> dict[str, Any]:
        return await _post_event(conn, path=PATH_PROCESS, body=event_body)

    tools.append(
        StructuredTool.from_function(
            name="process_data_collection_entries",
            description=(
                "Fire the ADP data-collection-entries.process event. Pass a full ADP event "
                "envelope (`{events: [...]}`) as `event_body`."
            ),
            coroutine=_process_data_collection_entries,
            args_schema=ProcessDataCollectionEntriesInput,
        ),
    )
    return tools


# ---------------------------------------------------------------------------
# Back-compat stub — preserved for __init__.py / test_bundle_init.py imports.

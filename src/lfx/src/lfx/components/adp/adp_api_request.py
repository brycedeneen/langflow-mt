"""ADPAPIRequestComponent — authenticated mTLS requests to api.adp.com."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.custom.custom_component.component import Component

if TYPE_CHECKING:
    import httpx
from lfx.io import (
    DataInput,
    DropdownInput,
    HandleInput,
    IntInput,
    MessageTextInput,
    Output,
    TabInput,
    TableInput,
)
from lfx.schema.data import Data

from ._shared import ADPConnection, build_mtls_httpx_client, fetch_token, validate_adp_url

# Endpoint catalog: display name → (path template, requires_id)
# ``{aoid}`` is substituted with resource_id when present; otherwise the
# ``requires_id`` flag decides whether to fail or to hit the list endpoint.
ENDPOINT_CATALOG: dict[str, tuple[str, bool]] = {
    "Workers": ("/hr/v2/workers", False),
    "Worker Demographics": ("/hr/v2/worker-demographics", False),
    "Pay Statements": ("/payroll/v1/workers/{aoid}/pay-statements", True),
    "Time Cards": ("/time/v2/workers/{aoid}/time-cards", True),
    "Jobs": ("/hr/v1/jobs", False),
    "Meta": ("/core/v1/meta", False),
    "Other (custom path)": ("", False),
}

MAX_PAGINATION_ITERATIONS = 1000
PAGE_SIZE_FOR_ALL = 100
HTTP_UNAUTHORIZED = 401
HTTP_CLIENT_ERROR_MIN = 400


class ADPAPIRequestComponent(Component):
    display_name = "ADP API Request"
    description = "Call ADP REST APIs using an ADPConnection. Authenticated with mTLS + Bearer token."
    icon = "Globe"
    name = "ADPAPIRequest"

    inputs = [
        HandleInput(
            name="connection",
            display_name="ADP Connection",
            input_types=["ADPConnection"],
            info="Connection produced by an ADP Auth component.",
            required=True,
        ),
        DropdownInput(
            name="endpoint",
            display_name="Endpoint",
            options=list(ENDPOINT_CATALOG.keys()),
            value="Workers",
            info="ADP API endpoint to call.",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="custom_path",
            display_name="Custom Path",
            info="Path (e.g. /hr/v2/workers) when Endpoint is 'Other'.",
            show=False,
        ),
        # TODO(follow-up): add update_build_config to show/hide custom_path when
        # endpoint == "Other (custom path)". Deferred per
        # docs/superpowers/plans/2026-04-14-adp-connector.md Task 10.
        MessageTextInput(
            name="resource_id",
            display_name="Resource ID (aoid)",
            info="Leave empty for list endpoints; set to a worker ID for by-ID lookups.",
        ),
        DropdownInput(
            name="method",
            display_name="HTTP Method",
            options=["GET", "POST", "PATCH", "PUT", "DELETE"],
            value="GET",
            advanced=True,
        ),
        DataInput(
            name="query_params",
            display_name="Query Parameters",
            info="Extra OData filters (e.g. $filter, $select).",
            advanced=True,
        ),
        TableInput(
            name="body",
            display_name="Body",
            info="Request body for non-GET methods.",
            table_schema=[
                {"name": "key", "display_name": "Key", "type": "str"},
                {"name": "value", "display_name": "Value"},
            ],
            value=[],
            advanced=True,
        ),
        TabInput(
            name="result_mode",
            display_name="Result Mode",
            options=["Top 20", "All"],
            value="Top 20",
            info="'Top 20' returns a single page of 20; 'All' auto-paginates.",
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            value=30,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="API Response", name="data", method="make_api_request"),
    ]

    def _build_json_body(self) -> dict[str, Any] | None:
        """Build JSON body dict from the `body` TableInput value. Returns None for GET."""
        rows = self.body or []
        if not isinstance(rows, list):
            return None
        result: dict[str, Any] = {}
        for row in rows:
            if not isinstance(row, dict) or "key" not in row or "value" not in row:
                continue
            result[row["key"]] = row["value"]
        return result or None

    def _resolve_path(self) -> str:
        endpoint = self.endpoint
        if endpoint == "Other (custom path)":
            path = (self.custom_path or "").strip()
            if not path:
                msg = "custom_path is required when Endpoint is 'Other (custom path)'"
                raise ValueError(msg)
            if not path.startswith("/"):
                path = "/" + path
            return path

        template, requires_id = ENDPOINT_CATALOG[endpoint]
        resource_id = (self.resource_id or "").strip()

        if "{aoid}" in template:
            if not resource_id:
                msg = f"resource_id is required for endpoint {endpoint!r}"
                raise ValueError(msg)
            return template.replace("{aoid}", resource_id)

        if requires_id and not resource_id:
            msg = f"resource_id is required for endpoint {endpoint!r}"
            raise ValueError(msg)

        if resource_id:
            return f"{template}/{resource_id}"
        return template

    def _build_query_params(self) -> dict[str, Any]:
        if self.query_params is None:
            return {}
        data = self.query_params.data or {} if hasattr(self.query_params, "data") else self.query_params
        if not isinstance(data, dict):
            return {}
        return dict(data)

    async def _execute_request(
        self,
        client: httpx.AsyncClient,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        params: dict[str, Any],
        json_body: Any,
        timeout: float,
    ) -> httpx.Response:
        return await client.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_body if method != "GET" else None,
            timeout=timeout,
        )

    async def make_api_request(self) -> Data:
        conn: ADPConnection = self.connection
        path = self._resolve_path()
        url = conn.api_base_url + path
        method = (self.method or "GET").upper()
        base_params = self._build_query_params()
        validate_adp_url(url, field_name="api_base_url")
        headers = {"Authorization": f"Bearer {conn.access_token}"}
        json_body = self._build_json_body() if method != "GET" else None

        if self.result_mode == "Top 20":
            params = {**base_params, "$top": 20}
            async with build_mtls_httpx_client(conn, timeout=self.timeout) as client:
                response = await self._call_with_401_retry(
                    client, method=method, url=url, headers=headers, params=params, conn=conn, json_body=json_body,
                )
                return self._response_to_data(url, response)

        # "All" mode — auto-paginate
        combined: dict[str, Any] = {}
        collection_key: str | None = None
        skip = 0
        iterations = 0
        final_response: httpx.Response | None = None

        async with build_mtls_httpx_client(conn, timeout=self.timeout) as client:
            while iterations < MAX_PAGINATION_ITERATIONS:
                iterations += 1
                params = {**base_params, "$top": PAGE_SIZE_FOR_ALL}
                if skip:
                    params["$skip"] = skip

                response = await self._call_with_401_retry(
                    client, method=method, url=url, headers=headers, params=params, conn=conn, json_body=json_body,
                )
                final_response = response

                if response.status_code >= HTTP_CLIENT_ERROR_MIN:
                    return self._response_to_data(url, response)

                try:
                    page = response.json()
                except ValueError:
                    return self._response_to_data(url, response)

                if collection_key is None:
                    collection_key = self._detect_collection_key(page)
                    combined = {collection_key: []} if collection_key else {}

                if not collection_key:
                    # Not a paginated collection — return single page
                    return self._response_to_data(url, response)

                items = page.get(collection_key, [])
                combined[collection_key].extend(items)

                if len(items) < PAGE_SIZE_FOR_ALL:
                    break
                skip += PAGE_SIZE_FOR_ALL

        return Data(
            data={
                "source": url,
                "status_code": final_response.status_code if final_response else 200,
                "result": combined,
            }
        )

    async def _call_with_401_retry(
        self,
        client: httpx.AsyncClient,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        params: dict[str, Any],
        conn: ADPConnection,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        response = await self._execute_request(
            client, method=method, url=url, headers=headers, params=params, json_body=json_body, timeout=self.timeout,
        )
        if response.status_code == HTTP_UNAUTHORIZED:
            await fetch_token(conn, force=True)
            headers["Authorization"] = f"Bearer {conn.access_token}"
            response = await self._execute_request(
                client,
                method=method,
                url=url,
                headers=headers,
                params=params,
                json_body=json_body,
                timeout=self.timeout,
            )
        return response

    @staticmethod
    def _detect_collection_key(page: Any) -> str | None:
        """ADP list responses wrap items in a top-level key (e.g. 'workers', 'items', 'payStatements').

        Heuristic: first key whose value is a list.
        """
        if not isinstance(page, dict):
            return None
        for k, v in page.items():
            if isinstance(v, list):
                return k
        return None

    def _response_to_data(self, url: str, response: httpx.Response) -> Data:
        try:
            body = response.json()
        except ValueError:
            body = response.text
        return Data(data={"source": url, "status_code": response.status_code, "result": body})

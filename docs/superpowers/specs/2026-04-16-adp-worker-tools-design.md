# ADP Worker Tools Component

## Overview

A Langflow component that takes an `ADPConnection` and outputs 5 `StructuredTool` instances for retrieving specific slices of employee data from the ADP `/hr/v2/workers/{associateOID}` API. Each tool calls the worker endpoint, extracts only its relevant fields, and returns a clean dict — so agents get focused data without parsing the full worker payload.

## Context

The existing `ADPAPIRequestComponent` returns raw API responses. For agent-driven workflows, tools that return targeted, pre-extracted data are more useful than raw JSON. This component sits alongside the existing ADP components and reuses the same `ADPConnection` / `_shared.py` infrastructure.

## Architecture

```
ADPAuthComponent ─→ ADPConnection ─→ ADPWorkerToolsComponent ─→ list[Tool] ─→ Agent
```

- **Input:** `ADPConnection` (from ADPAuthComponent) — carries credentials, token, mTLS certs
- **Output:** `list[Tool]` — 5 StructuredTool instances consumable by any Langflow Agent component

## File Location

`src/lfx/src/lfx/components/adp/adp_worker_tools.py`

Tests: `src/lfx/tests/unit/components/adp/test_adp_worker_tools.py`

## Tools

Each tool accepts `associate_oid: str` and returns a dict with extracted fields.

### get_employee_name

Extracts from `workers[0].person`.

Returns:
```json
{
  "legalName": {"firstName": "...", "middleName": "...", "lastName": "..."},
  "preferredName": {"firstName": "...", "lastName": "..."}
}
```

### get_employee_addresses

Extracts from `workers[0].person.legalAddress`.

Returns:
```json
{
  "legalAddress": {
    "lineOne": "...",
    "lineTwo": "...",
    "cityName": "...",
    "countrySubdivisionLevel1": "...",
    "postalCode": "...",
    "countryCode": "..."
  }
}
```

### get_employee_contact_information

Extracts from `workers[0].person.communication`.

Returns:
```json
{
  "emails": [{"emailUri": "...", "nameCode": {"codeValue": "..."}}],
  "landlines": [{"formattedNumber": "...", "nameCode": {"codeValue": "..."}}],
  "mobiles": [{"formattedNumber": "...", "nameCode": {"codeValue": "..."}}]
}
```

### get_employee_job

Extracts from `workers[0].workAssignments[0]`.

Returns:
```json
{
  "jobTitle": "...",
  "departmentName": "...",
  "locationName": "...",
  "workerStatus": "...",
  "managementPosition": false,
  "reportsTo": {"associateOID": "...", "workerName": "..."}
}
```

### get_employee_compensation

Extracts from `workers[0].workAssignments[0]`.

Returns:
```json
{
  "baseRemuneration": {
    "amount": "...",
    "currencyCode": "...",
    "frequency": "...",
    "effectiveDate": "..."
  },
  "additionalRemunerations": [
    {"amount": "...", "nameCode": {"codeValue": "..."}, "frequency": "..."}
  ]
}
```

## Internal Design

### Shared Worker Fetch

A private async method `_fetch_worker(conn, associate_oid)` on the component:

1. Builds mTLS httpx client via `build_mtls_httpx_client(conn)`
2. GETs `{conn.api_base_url}/hr/v2/workers/{associate_oid}` with Bearer token header
3. On 401: calls `fetch_token(conn, force=True)`, retries once
4. Returns the parsed JSON dict

Each tool function calls `_fetch_worker`, then runs its extraction logic.

### Tool Construction

At `build_tools()` time, the component creates 5 `StructuredTool.from_function` instances. Each uses a Pydantic `args_schema` with a single required field `associate_oid: str`.

The tool functions are async callables that close over the component instance (for access to `_fetch_worker` and the connection).

### Field Extraction

Each extraction function uses safe `.get()` chains so missing fields return `None` rather than raising. ADP API responses vary by client configuration — not every field is guaranteed present.

### Error Handling

- **401:** Auto-refresh token via `fetch_token(conn, force=True)`, retry once (matches existing component pattern)
- **Other HTTP errors:** Return error dict `{"error": "...", "status_code": N}` as tool response so the agent can communicate the failure
- **Invalid associate_oid:** Pydantic schema validation catches missing/empty values

## Testing

Unit tests in `test_adp_worker_tools.py`:

- Mock `_fetch_worker` to return sample worker JSON payloads
- Test each extraction function returns correct fields from a full worker response
- Test graceful handling of missing/partial fields (e.g., no preferredName, no additionalRemunerations)
- Test 401 retry logic on `_fetch_worker`
- Test HTTP error surfaces as error dict
- Test `build_tools` returns 5 tools with correct names and descriptions

## Registration

Add `ADPWorkerToolsComponent` to `__init__.py` exports alongside existing ADP components.

## Future Considerations

- Per-tool caching of worker responses (keyed by associate_oid with short TTL) if redundant API calls become a concern
- Additional tools for other worker sub-resources (pay statements, time cards)
- Migration to standalone MCP server outside Langflow (long-term goal)

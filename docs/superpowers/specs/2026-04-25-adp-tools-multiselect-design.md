# ADP Tools Multi-Select Consolidation

## Overview

Consolidate the 29 `ADP*ToolsComponent` classes into a single `ADPToolsComponent`. The user picks which tile groups (Worker, Pay Data Input, Time Off, …) to expose via a `MultiselectInput`, mirroring the pattern already used by `ADPTriggerComponent` for event types. Each selected tile contributes its existing `StructuredTool` set to the component's `list[Tool]` output, so the agent-facing surface is unchanged. As part of the consolidation, all read-only ADP API GETs go through a closure-scoped, URL-keyed request cache that eliminates duplicate roundtrips within a single `build_tools()` invocation.

## Context

The `lfx/components/adp/` directory currently ships 29 distinct `ADP*ToolsComponent` classes (~9.8K LOC across the directory). Every one of them has the same I/O shape: a `HandleInput` for `ADPConnection` in, an `Output` exposing `tools: list[Tool]` out. Browsing the component sidebar with 29 near-identical "ADP …" entries is noisy. There are no saved flows referencing any of these components yet, so this is the right window to collapse them before that constraint exists.

A second motivation surfaced during design: many tile classes contain multiple read tools that hit the **same** ADP endpoint. The most extreme example is `ADPWorkerToolsComponent`, whose 9 agent tools all call `GET /hr/v2/workers/{associateOID}` and slice different fields out of the response. Today an agent firing `get_employee_name` and `get_employee_compensation` for the same employee triggers two identical HTTP calls. Consolidation is the natural moment to fix this by introducing a shared per-build read cache.

## Scope

In scope: the **29 `adp_*_tools.py` files** and their `ADP*ToolsComponent` classes. Specifically:

- ADPApplicantOnboardingToolsComponent, ADPBenefitsToolsComponent, ADPDataCollectionEntriesToolsComponent, ADPDeductionConfigurationsToolsComponent, ADPJobApplicantsToolsComponent, ADPJobRequisitionsToolsComponent, ADPPayDataInputToolsComponent, ADPPayDistributionsToolsComponent, ADPPayStatementsToolsComponent, ADPTalentToolsComponent, ADPTeamTimeCardsToolsComponent, ADPTimeCardsToolsComponent, ADPTimeOffToolsComponent, ADPUSTaxProfilesToolsComponent, ADPWorkSchedulesToolsComponent, ADPWorkerAssignmentToolsComponent, ADPWorkerAssignmentV3ToolsComponent, ADPWorkerBiologicalToolsComponent, ADPWorkerBusinessCommunicationToolsComponent, ADPWorkerCompensationToolsComponent, ADPWorkerDemographicToolsComponent, ADPWorkerDeploymentToolsComponent, ADPWorkerHrProfilesToolsComponent, ADPWorkerIdentificationToolsComponent, ADPWorkerLeavesToolsComponent, ADPWorkerLifecycleToolsComponent, ADPWorkerPayrollInstructionsToolsComponent, ADPWorkerPersonalCommunicationToolsComponent, ADPWorkerToolsComponent.

Out of scope: `ADPAuthComponent` (produces the connection, not a tool), `ADPTriggerComponent` (webhook trigger, different category), `ADPAPIRequestComponent` (returns `Data`/`Message`, not StructuredTools), `ADPMCPComponent` (remote-defined tools via MCP, fundamentally different mechanism). These stay exactly as they are.

## Architecture

```
ADPAuthComponent ─→ ADPConnection ─┐
                                    ├─→ ADPToolsComponent ─→ list[Tool] ─→ Agent
                  (multi-select) ──┘
                  ["Worker", "Pay Data Input", ...]
```

- **One new component** at `src/lfx/src/lfx/components/adp/adp_tools.py` (display name `"ADP Tools"`, registered name `ADPTools`).
- **Inputs:** `HandleInput(connection)` (unchanged shape from existing tile components) + `MultiselectInput(tiles)` whose `options` are the 29 human-readable tile labels.
- **Output:** `Output(name="tools", method="build_tools")` returning `list[Tool]`.
- **Each existing `adp_*_tools.py`** is refactored to expose a single module-level `build_<tile>_tools(connection: ADPConnection, request_cache: RequestCache) -> list[Tool]` function and to no longer define a `Component` subclass.
- **Registry** in `adp_tools.py` maps `{label: builder}` for all 29 tiles. The unified component dispatches over the user's selected labels and concatenates the returned tool lists.
- **Shared request cache** lives in `_shared.py` and is constructed once per `build_tools()` call on the unified component. The cache is threaded into every selected tile's builder. Read-only HTTP GETs consult the cache via a `cached_get(...)` helper; writes bypass it entirely.

## The Unified Component

```python
# src/lfx/src/lfx/components/adp/adp_tools.py
from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from lfx.components.adp._shared import ADPConnection, RequestCache
from lfx.components.adp.adp_worker_tools import build_worker_tools
from lfx.components.adp.adp_pay_data_input_tools import build_pay_data_input_tools
# ... 26 more imports
from lfx.custom.custom_component.component import Component
from lfx.field_typing import Tool
from lfx.io import HandleInput, MultiselectInput, Output

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
                # Defensive: a label was removed from the registry but a saved flow still
                # references it. Skip silently rather than fail the whole build.
                continue
            tools.extend(builder(self.connection, cache))
        self.status = f"Exposing {len(tools)} tool(s) from {len(selected)} tile group(s)."
        return tools
```

### Tile Labels

Labels are short human-readable strings (not the existing class names). They appear in the multi-select picker. Loose grouping (Worker reads/admin, Worker mutations, Pay & Tax, Time, Talent & Recruiting, Other) is a navigational hint for users; it is not modeled in the registry — the dict order above defines display order.

## The Request Cache

New helper in `src/lfx/src/lfx/components/adp/_shared.py`:

```python
import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode


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
        items = sorted((query or {}).items())
        return f"{method.upper()} {url}?{urlencode(items, doseq=True)}"

    async def get_or_fetch(
        self, key: str, fetch: Callable[[], Awaitable[Any]],
    ) -> Any:
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
        self._entries[key] = _CacheEntry(
            expires_at=time.monotonic() + self._ttl, value=value,
        )
        self._entries.move_to_end(key)
        while len(self._entries) > self._max:
            evicted_key, _ = self._entries.popitem(last=False)
            self._locks.pop(evicted_key, None)
```

And a thin async helper for cached GETs:

```python
async def cached_get_json(
    *,
    client: httpx.AsyncClient,
    cache: RequestCache,
    url: str,
    headers: Mapping[str, str],
    params: Mapping[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Cache-aware JSON GET. Caches the parsed JSON dict on 2xx; on error,
    returns {"error": ..., "status_code": ...} and does NOT cache."""
    key = RequestCache.make_key("GET", url, params)

    async def _fetch() -> dict[str, Any]:
        response = await client.request(
            method="GET", url=url, headers=headers, params=params, timeout=timeout,
        )
        if response.status_code == HTTP_UNAUTHORIZED:
            # Token-refresh / retry happens inside the tile's _fetch wrapper, not here.
            return {"error": "unauthorized", "status_code": HTTP_UNAUTHORIZED}
        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            return {"error": detail, "status_code": response.status_code}
        return response.json()

    return await cache.get_or_fetch(key, _fetch)
```

### Cache Key & Isolation Rules (normative)

1. **Key from the resolved URL, never a route template.** `…/hr/v2/workers/G3X4Y5Z6` and `…/hr/v2/workers/A1B2C3D4` produce different keys by construction. Two employees can never collide.
2. **Query string is part of the key** (sorted, urlencoded), so any tool that distinguishes resources via query params is also disambiguated.
3. **Bearer token is never in the key.** The token rotates on 401 refresh; the underlying resource has not changed.
4. **Cache is closure-scoped to one `build_tools()` invocation.** That implicitly scopes it per-`ADPConnection`. Two `ADPAuth` components feeding two `ADPTools` components in the same flow get two independent caches → no cross-tenant leakage.
5. **Reads only.** Tools that mutate state (`POST`/`PATCH` to `/events/hr/v1/...`) call the httpx client directly and never touch the cache.
6. **Per-key `asyncio.Lock`** prevents thundering-herd refetches when an agent fires several tools in parallel.
7. **LRU eviction at 128 entries; TTL = 30s.** Both knobs are hard-coded constants on `ADPToolsComponent.build_tools()`. No invalidation API beyond TTL.

## Per-Tile Refactor Pattern

Take `adp_worker_tools.py` as the canonical example (highest cache-benefit tile: 9 read tools, 1 endpoint).

### Before

```python
class ADPWorkerToolsComponent(Component):
    display_name = "ADP Worker Tools"
    name = "ADPWorkerTools"
    icon = "Users"
    version: int = 2
    changelog: ClassVar[list[ChangelogEntry]] = [...]

    inputs = [HandleInput(name="connection", ...)]
    outputs = [Output(display_name="Tools", name="tools", method="build_tools")]

    async def _fetch_worker(self, conn: ADPConnection, associate_oid: str) -> dict[str, Any]:
        url = f"{conn.api_base_url}/hr/v2/workers/{associate_oid}"
        validate_adp_url(url, field_name="api_base_url")
        headers = {"Authorization": f"Bearer {conn.access_token}"}
        async with build_mtls_httpx_client(conn, timeout=30.0) as client:
            response = await self._execute_request(client, url=url, headers=headers, timeout=30.0)
            if response.status_code == HTTP_UNAUTHORIZED:
                await fetch_token(conn, force=True)
                headers["Authorization"] = f"Bearer {conn.access_token}"
                response = await self._execute_request(client, url=url, headers=headers, timeout=30.0)
        # ... error handling, return workers[0]

    async def build_tools(self) -> list[Tool]:
        conn: ADPConnection = self.connection
        component = self
        async def _get_employee_name(associate_oid: str) -> dict[str, Any]: ...
        # ... 8 more tool coroutines
        return [StructuredTool.from_function(...), ...]
```

### After

```python
# Module-level helpers stay exactly where they are: extract_name, extract_addresses,
# extract_contact_information, extract_job, extract_compensation, extract_ids,
# extract_dates, extract_status, extract_business_communication, _id_value, etc.

async def _fetch_worker(
    conn: ADPConnection, associate_oid: str, *, request_cache: RequestCache,
) -> dict[str, Any]:
    url = f"{conn.api_base_url}/hr/v2/workers/{associate_oid}"
    validate_adp_url(url, field_name="api_base_url")
    headers = {"Authorization": f"Bearer {conn.access_token}"}

    async def _do_fetch() -> dict[str, Any]:
        async with build_mtls_httpx_client(conn, timeout=30.0) as client:
            response = await client.request(method="GET", url=url, headers=headers, timeout=30.0)
            if response.status_code == HTTP_UNAUTHORIZED:
                await fetch_token(conn, force=True)
                headers["Authorization"] = f"Bearer {conn.access_token}"
                response = await client.request(method="GET", url=url, headers=headers, timeout=30.0)
        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            return {"error": detail, "status_code": response.status_code}
        data = response.json()
        workers = data.get("workers", [])
        if not workers:
            return {"error": "No worker found", "status_code": 404}
        return workers[0]

    key = RequestCache.make_key("GET", url, None)
    return await request_cache.get_or_fetch(key, _do_fetch)


def build_worker_tools(
    connection: ADPConnection, request_cache: RequestCache,
) -> list[Tool]:
    async def _get_employee_name(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_name(worker)

    # ... 8 more tool coroutines, identical pattern

    return [
        StructuredTool.from_function(
            name="get_employee_name",
            description="Get an employee's legal and preferred name by their ADP associate OID.",
            coroutine=_get_employee_name,
            args_schema=WorkerToolInput,
        ),
        # ... 8 more StructuredTool entries
    ]
```

### What Gets Deleted Per Tile File

- The `class ADP*ToolsComponent(Component): ...` definition and everything attached to it (`display_name`, `name`, `icon`, `version`, `changelog`, `inputs`, `outputs`).
- Imports of `Component`, `HandleInput`, `Output`, and `ChangelogEntry`.
- `ClassVar` typing import (no longer used after the changelog goes).
- The instance-method `_execute_request` indirection (rolled into the async closure).

### What Stays Per Tile File

- All `extract_*`, `_envelope`, `_phone_payload`, `_address_payload`-style helpers.
- All Pydantic input schemas (`WorkerToolInput`, `UpdateEmployeePhoneInput`, etc.).
- All `StructuredTool.from_function` definitions — relocated into the module-level `build_*_tools` function.
- All endpoint constants (`PATH_REHIRE`, etc.).

### Mutation Tiles

For tiles whose tools are entirely event POSTs (Compensation, Demographic, Personal Communication, etc.), the refactor is the same shape but the `request_cache` parameter is unused. The signature accepts it anyway for registry uniformity. Writes call `client.post`/`patch` directly; the cache is never touched.

## Cutover

Single PR, single commit:

1. Add `RequestCache` and `cached_get_json` to `_shared.py`.
2. Refactor each of the 29 `adp_*_tools.py` files: remove the `Component` subclass; lift `build_tools` body to a module-level `build_<tile>_tools(connection, request_cache)` function.
3. Add `adp_tools.py` with the registry (`TILE_BUILDERS`) and `ADPToolsComponent`.
4. Rewrite `adp/__init__.py`: drop the 29 `ADP*ToolsComponent` exports, add `ADPToolsComponent`. Keep `ADPAuthComponent`, `ADPTriggerComponent`, `ADPMCPComponent`, `ADPAPIRequestComponent` exactly as they are.
5. Update each existing tile test file: replace component-instantiation harnesses with direct `build_<tile>_tools(fake_connection, RequestCache())` calls. Per-tool behavior assertions stay identical.
6. Add `test_adp_tools.py`, `test_request_cache.py`, and `test_adp_tools_caching_e2e.py`.
7. Grep `STARTER_PROJECTS`, category JSON, and any sidebar metadata for references to the 29 deleted component names; remove them.

No flow-import migration is needed: per current project state, no saved flows reference any of the 29 components.

## Testing

### Per-tile builder tests (existing, refactored)

Each existing `tests/unit/components/adp/test_adp_*_tools.py` converts from "instantiate component, call `build_tools` on it" to "call `build_<tile>_tools(fake_connection, RequestCache())` directly and assert the returned `list[StructuredTool]` behaves identically." HTTP behavior assertions (mocked `httpx`, JSON shape, error paths, 401-refresh) stay verbatim. The `_shared.py` mocking surface (`build_mtls_httpx_client`, `fetch_token`, `validate_adp_url`) is unchanged.

### `test_adp_tools.py` (new)

- `test_no_selection_returns_empty_list` — empty `tiles` → `tools == []`, status string mentions zero tools.
- `test_single_tile_dispatch` — select `["Worker"]` → tool names match the 9 worker tool names exactly.
- `test_multiple_tile_dispatch` — select `["Worker", "Pay Data Input"]` → concatenated tool list, no duplicates, ordering matches selection order.
- `test_unknown_label_skipped` — select `["Worker", "GhostTile"]` → only Worker tools returned, no exception (defensive against stale saved flows).
- `test_registry_covers_all_29_tiles` — assert `len(TILE_BUILDERS) == 29` and every key appears in the `MultiselectInput.options` list. Drift guard.

### `test_request_cache.py` (new)

- `test_get_then_get_same_key_hits_once` — fetch fn is called once across two `get_or_fetch` calls within TTL.
- `test_ttl_expiry_refetches` — advance monotonic clock past TTL → fetch fn called again.
- `test_different_associate_oids_do_not_collide` — explicit regression guard for the correctness rule. Build keys for two `…/workers/{aoid}` URLs with different OIDs, assert distinct cache entries and distinct fetch invocations.
- `test_concurrent_get_or_fetch_locks_per_key` — `asyncio.gather` 10 concurrent `get_or_fetch` calls on the same key → fetch fn called exactly once.
- `test_lru_eviction_at_max` — exceed `max_entries` → oldest key evicted, lock map for the evicted key cleared.
- `test_bearer_token_not_in_key` — same URL, two different `Authorization` headers → identical cache key. Regression guard for rule (3).

### `test_adp_tools_caching_e2e.py` (new)

User-visible payoff test for the caching strategy. Mock the ADP `/hr/v2/workers/{aoid}` endpoint with a request counter. Build the unified component selecting `["Worker"]`. Take the 9 returned tools and invoke 5 of them on the same `aoid`. Assert the mock endpoint was hit **once**, not five times. Repeat the test invoking on two different `aoid`s and assert the mock was hit exactly twice.

### Test environment

Per `reference_lfx_test_env.md`: `LFX_TEST_ALLOW_LANGFLOW=1` permits running the `src/lfx` ADP test suite from the repo-level venv.

## Out of Scope

- **ADP Assist agent metadata.** The bootstrap script in flight (`docs/superpowers/specs/2026-04-21-adp-assist-per-component-design.md`) keys off the component class. It will regenerate metadata for `ADPToolsComponent` next time it runs. We seed a stub `assist_examples` and let the bootstrap fill in the body.
- **`ADPMCPComponent` consolidation.** Different mechanism (remote-defined tools via MCP). Per memory `project_adp_mcp_live_deferred.md`, ADP's MCP server is a long way off; the component is a stub.
- **Cross-component-instance caching.** Two `ADPToolsComponent` instances in one flow get two independent caches by design. Closure scoping is the isolation primitive; users wanting a shared cache should use one component.
- **Cache invalidation on writes.** TTL-only. Mutations skip the cache outbound; reads tolerate up to ~30s staleness. If this proves to bite, add explicit per-aoid invalidation in a follow-up.
- **Granular per-tool selection inside a tile.** The multi-select operates at whole-tile grain. If a user wants only `get_employee_name` from `Worker`, they get the full Worker tile. Per-tool trimming can come later if anyone asks.
- **Migration of existing saved flows.** None reference any of the 29 deprecated components today, so no migration is required.

## Risks

- **Mass mechanical refactor.** 29 files touched in one PR. Mitigation: each tile refactor is isolated (one file in, same set of `StructuredTool`s out), and the per-tile tests preserve full behavior coverage. Land tile-by-tile within the PR if review prefers smaller diffs per file.
- **Stale labels in saved flows.** If a tile is renamed or removed in a later release, saved flows holding the old label silently produce zero tools for that label. The unknown-label-skip behavior is defensive but could mask the issue from the user. Acceptable for now; revisit if it bites.
- **Cache TTL too long for write-heavy agent loops.** A 30s TTL means an agent doing "write then read again" within 30s sees stale data. Mitigation: TTL is conservative (most agent turns finish in <30s) and write-then-immediately-read is rare in practice. If this regresses real usage, add explicit invalidation.

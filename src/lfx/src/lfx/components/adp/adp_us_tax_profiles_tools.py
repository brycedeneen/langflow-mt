"""ADPUSTaxProfilesToolsComponent — consolidated US tax profile reads + writes.

Combines ADP WFN `payroll/us-tax-profiles v1` (reads + federal/local writes) and
`payroll/us-tax-profiles v2` (state writes) into one component with two tools:

- `get_worker_us_tax_profile` (read; `view: Literal["summary", "state", "local"]`)
- `manage_worker_us_tax_instruction` (write, gated; consolidates federal/local/state
  add/change/remove across both v1 + v2 event endpoints)
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from lfx.components.adp._shared import ADPConnection, build_mtls_httpx_client, fetch_token, validate_adp_url
from lfx.custom.custom_component.changelog import ChangelogEntry
from lfx.custom.custom_component.component import Component
from lfx.field_typing import Tool
from lfx.io import BoolInput, HandleInput, Output

HTTP_UNAUTHORIZED = 401
HTTP_CLIENT_ERROR_MIN = 400

TaxView = Literal["summary", "state", "local"]
TaxJurisdiction = Literal["federal", "state", "local"]
TaxAction = Literal["add", "change", "remove"]

# Each (jurisdiction, action) tuple either maps to a path or None (unsupported
# per spec — only federal.change / state.add+change / local.add+change+remove).
_EVENT_PATHS: dict[tuple[str, str], str] = {
    ("federal", "change"): "/events/payroll/v1/us-tax-profile.federal-income-tax-instruction.change",
    ("state", "add"): "/events/payroll/v2/us-tax-profile.state-income-tax-instruction.add",
    ("state", "change"): "/events/payroll/v2/us-tax-profile.state-income-tax-instruction.change",
    ("local", "add"): "/events/payroll/v1/us-tax-profile.local-income-tax-instruction.add",
    ("local", "change"): "/events/payroll/v1/us-tax-profile.local-income-tax-instruction.change",
    ("local", "remove"): "/events/payroll/v1/us-tax-profile.local-income-tax-instruction.remove",
}

_READ_PATHS: dict[str, str] = {
    "summary": "/payroll/v1/workers/{aoid}/us-tax-profiles",
    "state": "/payroll/v1/workers/{aoid}/us-tax-profiles/{profile_id}/state",
    "local": "/payroll/v1/workers/{aoid}/us-tax-profiles/{profile_id}/local",
}

_TRANSFORM_KEYS: dict[str, str] = {
    "federal": "federalIncomeTaxInstruction",
    "state": "stateIncomeTaxInstruction",
    "local": "localIncomeTaxInstruction",
}


def event_path(jurisdiction: TaxJurisdiction, action: TaxAction) -> str:
    try:
        return _EVENT_PATHS[(jurisdiction, action)]
    except KeyError as err:
        msg = f"Unsupported (jurisdiction, action) combination: ({jurisdiction!r}, {action!r})"
        raise ValueError(msg) from err


def build_tax_instruction_event(
    *,
    jurisdiction: TaxJurisdiction,
    action: TaxAction,
    associate_oid: str,
    fields: dict[str, Any] | None = None,
    item_id: str | None = None,
    context_pin_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    transform_key = _TRANSFORM_KEYS[jurisdiction]

    event_context: dict[str, Any] = {"worker": {"associateOID": associate_oid}}
    if action in ("change", "remove"):
        pin: dict[str, Any] = {}
        if item_id:
            pin["itemID"] = item_id
        if context_pin_fields:
            for k, v in context_pin_fields.items():
                pin[k] = v
        if action == "remove" and not pin:
            msg = "'remove' action requires item_id or context_pin_fields"
            raise ValueError(msg)
        if pin:
            event_context[transform_key] = pin

    data: dict[str, Any] = {"eventContext": event_context}
    if action in ("add", "change"):
        data["transform"] = {transform_key: dict(fields or {})}

    return {"events": [{"data": data}]}


class GetWorkerUSTaxProfileInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID of the worker.")
    view: TaxView = Field(
        description=(
            "Which projection: 'summary' (the full profile at /us-tax-profiles), 'state' (state "
            "sub-resource, requires profile_id), 'local' (local sub-resource, requires profile_id)."
        ),
    )
    profile_id: str | None = Field(
        default=None,
        description="us-tax-profile ID, required when view is 'state' or 'local'.",
    )


class ManageWorkerUSTaxInstructionInput(BaseModel):
    jurisdiction: TaxJurisdiction = Field(
        description=(
            "Tax jurisdiction: 'federal' (change only), 'state' (add/change), or 'local' "
            "(add/change/remove)."
        ),
    )
    action: TaxAction = Field(description="Event to fire: 'add', 'change', or 'remove'.")
    associate_oid: str = Field(description="ADP associate OID of the worker.")
    item_id: str | None = Field(
        default=None,
        description="Existing tax-instruction itemID (required for change/remove).",
    )
    fields: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Transform payload under the jurisdiction-specific key. Typical fields: "
            "taxCodeFilingStatusCode, taxMaritalStatusCode, taxExemptionAllowancesQuantity, "
            "additionalTaxAmount, taxAuthorityCode (state/local), etc. Pass ADP-shaped dicts."
        ),
    )
    context_pin_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Fields to pin the instruction in eventContext (alongside or instead of item_id).",
    )


class ADPUSTaxProfilesToolsComponent(Component):
    display_name = "ADP US Tax Profiles Tools"
    description = (
        "Consolidated US tax-profile reads + writes across ADP WFN us-tax-profiles v1 and v2. "
        "`get_worker_us_tax_profile` returns the summary, state, or local view. "
        "`manage_worker_us_tax_instruction` handles federal/state/local add/change/remove "
        "via `jurisdiction` + `action` literals. Mutations gated behind `enable_mutations`."
    )
    icon = "FileText"
    name = "ADPUSTaxProfilesTools"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release — 2 consolidated agent tools covering us-tax-profiles v1 reads "
                "+ v1/v2 mutation events across federal/state/local jurisdictions. Mutation "
                "gated behind `enable_mutations`."
            ),
        ),
    ]

    inputs = [
        HandleInput(
            name="connection",
            display_name="ADP Connection",
            input_types=["ADPConnection"],
            info="Connection produced by an ADP Auth component.",
            required=True,
        ),
        BoolInput(
            name="enable_mutations",
            display_name="Enable Mutations",
            info="Expose the tax-instruction manage tool. Off by default.",
            value=False,
        ),
    ]

    outputs = [
        Output(display_name="Tools", name="tools", method="build_tools"),
    ]

    async def _execute_request(
        self, client: httpx.AsyncClient, *, method: str, url: str, headers: dict[str, str],
        json_body: dict[str, Any] | None, timeout: float,
    ) -> httpx.Response:
        return await client.request(method=method, url=url, headers=headers, json=json_body, timeout=timeout)

    async def _call(
        self, conn: ADPConnection, *, method: str, path: str, body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{conn.api_base_url}{path}"
        validate_adp_url(url, field_name="api_base_url")
        headers = {"Authorization": f"Bearer {conn.access_token}"}

        async with build_mtls_httpx_client(conn, timeout=30.0) as client:
            response = await self._execute_request(
                client, method=method, url=url, headers=headers, json_body=body, timeout=30.0,
            )
            if response.status_code == HTTP_UNAUTHORIZED:
                await fetch_token(conn, force=True)
                headers["Authorization"] = f"Bearer {conn.access_token}"
                response = await self._execute_request(
                    client, method=method, url=url, headers=headers, json_body=body, timeout=30.0,
                )

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

    async def _post_event(self, conn: ADPConnection, *, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._call(conn, method="POST", path=path, body=body)

    async def build_tools(self) -> list[Tool]:
        conn: ADPConnection = self.connection
        component = self

        async def _get_worker_us_tax_profile(
            associate_oid: str, view: str, profile_id: str | None = None,
        ) -> dict[str, Any]:
            template = _READ_PATHS[view]
            if view in ("state", "local"):
                if not profile_id:
                    return {"error": f"profile_id required for view={view!r}", "status_code": 422}
                path = template.format(aoid=associate_oid, profile_id=profile_id)
            else:
                path = template.format(aoid=associate_oid)
            return await component._call(conn, method="GET", path=path)

        tools: list[Tool] = [
            StructuredTool.from_function(
                name="get_worker_us_tax_profile",
                description=(
                    "Get a worker's US tax profile. `view='summary'` for the profile overview, "
                    "`'state'` or `'local'` to drill into a specific profile's sub-resource "
                    "(both require `profile_id`)."
                ),
                coroutine=_get_worker_us_tax_profile,
                args_schema=GetWorkerUSTaxProfileInput,
            ),
        ]

        if not self.enable_mutations:
            return tools

        async def _manage_worker_us_tax_instruction(**kwargs: Any) -> dict[str, Any]:
            jurisdiction = kwargs["jurisdiction"]
            action = kwargs["action"]
            try:
                body = build_tax_instruction_event(
                    jurisdiction=jurisdiction,
                    action=action,
                    associate_oid=kwargs["associate_oid"],
                    fields=kwargs.get("fields") or {},
                    item_id=kwargs.get("item_id"),
                    context_pin_fields=kwargs.get("context_pin_fields") or {},
                )
                path = event_path(jurisdiction, action)
            except ValueError as err:
                return {"error": str(err), "status_code": 422}
            return await component._post_event(conn, path=path, body=body)

        tools.append(
            StructuredTool.from_function(
                name="manage_worker_us_tax_instruction",
                description=(
                    "Fire a US tax-instruction event. Supported combos: federal/change, "
                    "state/(add|change), local/(add|change|remove). Pass `fields` with the "
                    "ADP-shaped transform payload; include `item_id` for change/remove."
                ),
                coroutine=_manage_worker_us_tax_instruction,
                args_schema=ManageWorkerUSTaxInstructionInput,
            ),
        )
        return tools

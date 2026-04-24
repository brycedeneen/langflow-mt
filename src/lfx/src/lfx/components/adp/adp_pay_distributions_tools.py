"""ADPPayDistributionsToolsComponent — pay-distribution read + change tools.

Backs the ADP WFN `payroll/pay-distributions v2` tile. Exposes:

- `get_worker_pay_distributions` (read; list + detail consolidated)
- `change_worker_pay_distributions` (write; gated behind `enable_mutations`)

The change endpoint handles add/update/inactivate/remove-all via the
`distributionInstructions` array shape: no itemID = add, itemID = update,
`instructionStatusCode=I` = inactivate, empty array = remove all. US vs
Canadian accounts differ only in the `financialParty` sub-shape.
"""

from __future__ import annotations

from typing import Any, ClassVar

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

PATH_LIST = "/payroll/v2/workers/{aoid}/pay-distributions"
PATH_DETAIL = "/payroll/v2/workers/{aoid}/pay-distributions/{pay_distribution_id}"
PATH_CHANGE = "/events/payroll/v1/worker.pay-distribution.change"


def _build_deposit_account(instruction: dict[str, Any]) -> dict[str, Any]:
    account: dict[str, Any] = {}

    financial_account: dict[str, Any] = {}
    if instruction.get("account_number") is not None:
        financial_account["accountNumber"] = instruction["account_number"]
    if instruction.get("account_type_code") is not None:
        financial_account["typeCode"] = {"codeValue": instruction["account_type_code"]}
        if instruction.get("account_type_short_name"):
            financial_account["typeCode"]["shortName"] = instruction["account_type_short_name"]
    if financial_account:
        account["financialAccount"] = financial_account

    financial_party: dict[str, Any] = {}
    # US style
    if instruction.get("routing_transit_id"):
        financial_party["routingTransitID"] = {"idValue": instruction["routing_transit_id"]}
    # Canadian style
    if instruction.get("financial_party_scheme_code"):
        financial_party["financialPartyID"] = {
            "schemeCode": {"codeValue": instruction["financial_party_scheme_code"]},
        }
    if instruction.get("branch_name_code"):
        financial_party["branchNameCode"] = {"codeValue": instruction["branch_name_code"]}

    if financial_party:
        account["financialParty"] = financial_party

    return account


def _format_numeric(value: Any) -> str:
    """Render numeric as string, dropping the trailing `.0` for whole numbers.

    HAR examples show ADP expects e.g. `"50"` for percentages rather than
    `"50.0"` — keep the string form stable regardless of whether callers pass
    ints, floats, or already-formatted strings.
    """
    if isinstance(value, str):
        return value
    f = float(value)
    return str(int(f)) if f.is_integer() else str(f)


def _build_distribution_instruction(item: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if item.get("item_id"):
        out["itemID"] = item["item_id"]
    if item.get("distribution_percentage") is not None:
        out["distributionPercentage"] = _format_numeric(item["distribution_percentage"])
    if item.get("distribution_amount") is not None:
        out["distributionAmount"] = {"amountValue": _format_numeric(item["distribution_amount"])}
    if item.get("remaining_balance_indicator"):
        out["remainingBalanceIndicator"] = True
    if item.get("instruction_status_code"):
        status: dict[str, Any] = {"codeValue": item["instruction_status_code"]}
        if item.get("instruction_status_short_name"):
            status["shortName"] = item["instruction_status_short_name"]
        out["instructionStatusCode"] = status

    deposit_account = _build_deposit_account(item)
    if deposit_account:
        out["depositAccount"] = deposit_account
    return out


def build_change_pay_distribution_event(
    *,
    associate_oid: str,
    work_assignment_item_id: str,
    distribution_instructions: list[dict[str, Any]] | None = None,
    effective_date: str | None = None,
    additional_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pay_distribution: dict[str, Any] = {
        "distributionInstructions": [
            _build_distribution_instruction(i) for i in (distribution_instructions or [])
        ],
    }
    if additional_fields:
        for key, value in additional_fields.items():
            pay_distribution[key] = value

    transform: dict[str, Any] = {"payDistribution": pay_distribution}
    if effective_date:
        transform["effectiveDateTime"] = effective_date

    return {
        "events": [
            {
                "data": {
                    "eventContext": {
                        "worker": {"associateOID": associate_oid},
                        "payDistribution": {"itemID": work_assignment_item_id},
                    },
                    "transform": transform,
                },
            },
        ],
    }


class GetPayDistributionsInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID of the worker.")
    pay_distribution_id: str | None = Field(
        default=None,
        description="Specific pay-distribution ID to fetch. Omit to list all for the worker.",
    )


class DistributionInstruction(BaseModel):
    item_id: str | None = Field(
        default=None,
        description="Existing instruction itemID (from a prior list call). Omit to add a new instruction.",
    )
    distribution_percentage: float | None = Field(
        default=None,
        description="Percentage of net pay for this instruction (e.g. 50 for 50%). Mutually exclusive with amount/remaining.",
    )
    distribution_amount: float | None = Field(
        default=None,
        description="Fixed partial-net amount for this instruction. Mutually exclusive with percentage/remaining.",
    )
    remaining_balance_indicator: bool = Field(
        default=False,
        description="True if this instruction takes the remaining (full-net) balance. Mutually exclusive with percentage/amount.",
    )
    instruction_status_code: str | None = Field(
        default=None,
        description="Status code — e.g. 'I' to inactivate. Omit for active.",
    )
    instruction_status_short_name: str | None = Field(
        default=None, description="Optional short name paired with status code (e.g. 'Inactive').",
    )
    account_number: str | None = Field(default=None, description="Deposit account number.")
    account_type_code: str | None = Field(
        default=None,
        description="Deposit type code (typically a single letter like 'x','W','Y','Z' for US; 'DP1'-'DP5' for CA).",
    )
    account_type_short_name: str | None = Field(
        default=None, description="Optional short name for the deposit type (e.g. 'DEPOSIT ACCT1').",
    )
    routing_transit_id: str | None = Field(
        default=None,
        description="US routing/transit number. Use for US clients.",
    )
    financial_party_scheme_code: str | None = Field(
        default=None,
        description="Canadian institution scheme code (e.g. '260'). Use for Canadian clients.",
    )
    branch_name_code: str | None = Field(
        default=None, description="Canadian branch/transit number. Use with scheme code.",
    )


class ChangePayDistributionsInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID of the worker.")
    work_assignment_item_id: str = Field(
        description="Work-assignment itemID (from the worker's work assignments; acts as the pay-distribution scope).",
    )
    distribution_instructions: list[DistributionInstruction] = Field(
        default_factory=list,
        description="Full list of distribution instructions for this worker. Pass [] to remove all direct-deposit instructions.",
    )
    effective_date: str | None = Field(default=None, description="ISO-8601 effective date (YYYY-MM-DD).")
    additional_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Escape hatch: extra fields merged into the payDistribution object for rare payload shapes.",
    )


class ADPPayDistributionsToolsComponent(Component):
    display_name = "ADP Pay Distributions Tools"
    description = (
        "Read + change tools for ADP WFN `payroll/pay-distributions v2`. "
        "`get_worker_pay_distributions` lists or fetches a worker's direct-deposit "
        "distributions. `change_worker_pay_distributions` handles add/update/inactivate/remove-all "
        "via a single instructions array; gated behind `enable_mutations`."
    )
    icon = "Banknote"
    name = "ADPPayDistributionsTools"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release — 2 agent tools for ADP WFN payroll/pay-distributions v2: "
                "`get_worker_pay_distributions` (list + detail) and `change_worker_pay_distributions` "
                "(consolidated add/update/inactivate/remove-all). Mutation gated behind the "
                "`enable_mutations` input (default off)."
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
            info=(
                "Expose the change-pay-distributions tool to the agent. Off by default — "
                "direct-deposit changes are high-blast-radius. Turn on only when the flow is "
                "meant to act on pay-distribution data."
            ),
            value=False,
        ),
    ]

    outputs = [
        Output(display_name="Tools", name="tools", method="build_tools"),
    ]

    async def _execute_request(
        self,
        client: httpx.AsyncClient,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any] | None,
        timeout: float,
    ) -> httpx.Response:
        return await client.request(
            method=method,
            url=url,
            headers=headers,
            json=json_body,
            timeout=timeout,
        )

    async def _call(
        self,
        conn: ADPConnection,
        *,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
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

        async def _get_worker_pay_distributions(
            associate_oid: str, pay_distribution_id: str | None = None,
        ) -> dict[str, Any]:
            if pay_distribution_id:
                path = PATH_DETAIL.format(aoid=associate_oid, pay_distribution_id=pay_distribution_id)
            else:
                path = PATH_LIST.format(aoid=associate_oid)
            return await component._call(conn, method="GET", path=path)

        tools: list[Tool] = [
            StructuredTool.from_function(
                name="get_worker_pay_distributions",
                description=(
                    "Get a worker's pay-distribution (direct-deposit) instructions. If "
                    "`pay_distribution_id` is provided, fetches that single distribution; "
                    "otherwise lists all distributions for the worker. Each instruction includes "
                    "itemID (pass to `change_worker_pay_distributions` as `item_id` to update), "
                    "distribution amount/percentage/remaining-balance, and deposit account."
                ),
                coroutine=_get_worker_pay_distributions,
                args_schema=GetPayDistributionsInput,
            ),
        ]

        if not self.enable_mutations:
            return tools

        async def _change_worker_pay_distributions(**kwargs: Any) -> dict[str, Any]:
            normalized = dict(kwargs)
            items = normalized.get("distribution_instructions") or []
            normalized["distribution_instructions"] = [
                item.model_dump() if hasattr(item, "model_dump") else item for item in items
            ]
            body = build_change_pay_distribution_event(**normalized)
            return await component._post_event(conn, path=PATH_CHANGE, body=body)

        tools.append(
            StructuredTool.from_function(
                name="change_worker_pay_distributions",
                description=(
                    "Change a worker's pay-distribution (direct-deposit) instructions. Handles "
                    "add (omit item_id), update (include item_id), inactivate (include item_id + "
                    "instruction_status_code='I'), and remove-all (pass an empty "
                    "distribution_instructions list). For US accounts use routing_transit_id; for "
                    "Canadian accounts use financial_party_scheme_code + branch_name_code. Requires "
                    "the worker's associate_oid and work_assignment_item_id."
                ),
                coroutine=_change_worker_pay_distributions,
                args_schema=ChangePayDistributionsInput,
            ),
        )

        return tools

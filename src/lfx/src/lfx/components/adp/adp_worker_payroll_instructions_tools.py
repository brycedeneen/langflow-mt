"""ADPWorkerPayrollInstructionsToolsComponent — payroll-instruction read + general-deduction tools.

Backs the ADP WFN `payroll/worker-payroll-instructions v1` tile. Exposes:

- `get_worker_payroll_instructions` (read; list + detail consolidated)
- `manage_worker_general_deduction` (write; gated — consolidates start/change/stop)

The tile's reads cover all payroll-instruction types (general deductions,
garnishments, memos, earnings, benefits, retirement). The mutation endpoints
only cover general deductions, so the single write tool is scoped accordingly.
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

PATH_LIST = "/payroll/v1/workers/{aoid}/payroll-instructions"
PATH_DETAIL = "/payroll/v1/workers/{aoid}/payroll-instructions/{payroll_instruction_id}"
PATH_START = "/events/payroll/v2/worker-general-deduction-instruction.start"
PATH_CHANGE = "/events/payroll/v2/worker-general-deduction-instruction.change"
PATH_STOP = "/events/payroll/v2/worker-general-deduction-instruction.stop"

_ACTION_PATHS: dict[str, str] = {
    "start": PATH_START,
    "change": PATH_CHANGE,
    "stop": PATH_STOP,
}


def _amount(amount_value: Any, currency_code: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"amountValue": amount_value}
    if currency_code:
        out["currencyCode"] = currency_code
    return out


def _build_deduction_goal(goal: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if goal.get("goal_limit_amount") is not None:
        out["goalLimitAmount"] = _amount(goal["goal_limit_amount"], goal.get("currency_code"))
    if goal.get("goal_id") is not None:
        out["goalID"] = goal["goal_id"]
    if goal.get("goal_balance_amount") is not None:
        out["goalBalanceAmount"] = _amount(goal["goal_balance_amount"], goal.get("currency_code"))
    return out


def _build_general_deduction_payload(
    *,
    deduction_code: str | None,
    deduction_rate_value: Any,
    deduction_rate_currency: str | None,
    inactive_indicator: bool | None,
    deduction_goal: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if deduction_code is not None:
        payload["deductionCode"] = {"codeValue": deduction_code}
    if deduction_rate_value is not None:
        rate: dict[str, Any] = {"rateValue": deduction_rate_value}
        if deduction_rate_currency:
            rate["currencyCode"] = deduction_rate_currency
        payload["deductionRate"] = rate
    if inactive_indicator is not None:
        payload["inactiveIndicator"] = inactive_indicator
    if deduction_goal:
        goal_payload = _build_deduction_goal(deduction_goal)
        if goal_payload:
            payload["deductionGoal"] = goal_payload
    return payload


def build_general_deduction_event(  # noqa: C901, PLR0912
    *,
    action: Literal["start", "change", "stop"],
    associate_oid: str,
    payroll_file_number: str,
    payroll_agreement_id: str,
    effective_date: str | None = None,
    payroll_group_code: str | None = None,
    payroll_group_short_name: str | None = None,
    item_id: str | None = None,
    deduction_code: str | None = None,
    deduction_rate_value: Any = None,
    deduction_rate_currency: str | None = None,
    inactive_indicator: bool | None = None,
    deduction_goal: dict[str, Any] | None = None,
    additional_context_fields: dict[str, Any] | None = None,
    additional_transform_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # eventContext.payrollInstruction
    ctx_payroll_instruction: dict[str, Any] = {
        "payrollFileNumber": payroll_file_number,
        "payrollAgreementID": payroll_agreement_id,
    }
    if payroll_group_code:
        group_code: dict[str, Any] = {"codeValue": payroll_group_code}
        if payroll_group_short_name:
            group_code["shortName"] = payroll_group_short_name
        ctx_payroll_instruction["payrollGroupCode"] = group_code

    if action in ("change", "stop"):
        if not item_id:
            msg = f"{action!r} action requires item_id"
            raise ValueError(msg)
        ctx_payroll_instruction["itemID"] = item_id

    # For change/stop, the eventContext pins the generalDeductionInstruction (with a
    # deduction code on change; empty {} on stop).
    if action == "change":
        if deduction_code is None:
            msg = "'change' action requires deduction_code (to identify the instruction in context)"
            raise ValueError(msg)
        ctx_payroll_instruction["generalDeductionInstruction"] = {
            "deductionCode": {"codeValue": deduction_code},
        }
    elif action == "stop":
        ctx_payroll_instruction["generalDeductionInstruction"] = {}

    if additional_context_fields:
        for key, value in additional_context_fields.items():
            ctx_payroll_instruction[key] = value

    event_context: dict[str, Any] = {
        "worker": {"associateOID": associate_oid},
        "payrollInstruction": ctx_payroll_instruction,
    }

    # transform
    transform: dict[str, Any] = {}
    if effective_date:
        transform["effectiveDateTime"] = effective_date

    if action in ("start", "change"):
        # For start, deduction_code goes in the transform payload; for change,
        # deduction_code is pinned in eventContext so the transform only carries
        # the fields being changed.
        gdi = _build_general_deduction_payload(
            deduction_code=deduction_code if action == "start" else None,
            deduction_rate_value=deduction_rate_value,
            deduction_rate_currency=deduction_rate_currency,
            inactive_indicator=inactive_indicator,
            deduction_goal=deduction_goal,
        )
        if gdi:
            transform["payrollInstruction"] = {"generalDeductionInstruction": gdi}

    if additional_transform_fields:
        for key, value in additional_transform_fields.items():
            transform[key] = value

    return {
        "events": [
            {
                "data": {
                    "eventContext": event_context,
                    "transform": transform,
                },
            },
        ],
    }


class GetPayrollInstructionsInput(BaseModel):
    associate_oid: str = Field(description="ADP associate OID of the worker.")
    payroll_instruction_id: str | None = Field(
        default=None,
        description="Specific payroll-instruction ID to fetch. Omit to list all for the worker.",
    )


class DeductionGoal(BaseModel):
    goal_limit_amount: float | None = Field(default=None, description="Total goal/cap amount.")
    goal_id: str | None = Field(default=None, description="Goal identifier (1–9 per ADP docs).")
    goal_balance_amount: float | None = Field(default=None, description="Current goal balance (already deducted).")
    currency_code: str | None = Field(
        default=None, description="ISO-4217 currency code. Omit to match HAR examples (ADP infers).",
    )


class ManageGeneralDeductionInput(BaseModel):
    action: Literal["start", "change", "stop"] = Field(
        description=(
            "Which event to fire: 'start' (add a new general deduction), 'change' (modify an "
            "existing one), or 'stop' (end one)."
        ),
    )
    associate_oid: str = Field(description="ADP associate OID of the worker.")
    payroll_file_number: str = Field(description="Worker's payroll file number.")
    payroll_agreement_id: str = Field(description="Worker's payroll agreement ID.")
    effective_date: str | None = Field(
        default=None, description="ISO-8601 effective date (YYYY-MM-DD). Required by ADP for all three actions.",
    )
    payroll_group_code: str | None = Field(
        default=None,
        description="Payroll group code (e.g. '94N'). Required for start/change. Omit for stop.",
    )
    payroll_group_short_name: str | None = Field(
        default=None, description="Optional short name paired with payroll group code.",
    )
    item_id: str | None = Field(
        default=None,
        description="Deduction instruction itemID (from a prior list call). Required for change/stop.",
    )
    deduction_code: str | None = Field(
        default=None,
        description="Deduction code (e.g. 'H', 'M', 'D'). Required for start and change.",
    )
    deduction_rate_value: float | None = Field(
        default=None, description="Deduction amount/rate. Required for start; optional for change.",
    )
    deduction_rate_currency: str | None = Field(
        default=None, description="ISO-4217 currency for the rate. Typically 'USD'; optional.",
    )
    inactive_indicator: bool | None = Field(
        default=None, description="If true, the instruction is recorded as inactive.",
    )
    deduction_goal: DeductionGoal | None = Field(
        default=None, description="Optional goal (limit, id, running balance).",
    )
    additional_context_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Escape hatch: extra fields merged into eventContext.payrollInstruction.",
    )
    additional_transform_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Escape hatch: extra fields merged into transform.",
    )


class ADPWorkerPayrollInstructionsToolsComponent(Component):
    display_name = "ADP Worker Payroll Instructions Tools"
    description = (
        "Read + general-deduction management tools for ADP WFN "
        "`payroll/worker-payroll-instructions v1`. `get_worker_payroll_instructions` lists "
        "or fetches a worker's payroll instructions. `manage_worker_general_deduction` "
        "consolidates start/change/stop into one tool; gated behind `enable_mutations`."
    )
    icon = "Receipt"
    name = "ADPWorkerPayrollInstructionsTools"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release — 2 agent tools for ADP WFN payroll/worker-payroll-instructions "
                "v1: `get_worker_payroll_instructions` (list + detail) and "
                "`manage_worker_general_deduction` (consolidated start/change/stop via an "
                "`action` literal). Mutation gated behind the `enable_mutations` input "
                "(default off)."
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
                "Expose the general-deduction management tool to the agent. Off by default — "
                "deduction changes are high-blast-radius. Turn on only when the flow is meant "
                "to act on deduction data."
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

        async def _get_worker_payroll_instructions(
            associate_oid: str, payroll_instruction_id: str | None = None,
        ) -> dict[str, Any]:
            if payroll_instruction_id:
                path = PATH_DETAIL.format(
                    aoid=associate_oid, payroll_instruction_id=payroll_instruction_id,
                )
            else:
                path = PATH_LIST.format(aoid=associate_oid)
            return await component._call(conn, method="GET", path=path)

        tools: list[Tool] = [
            StructuredTool.from_function(
                name="get_worker_payroll_instructions",
                description=(
                    "Get a worker's payroll instructions (general deductions, garnishments, memos, "
                    "earnings, benefits, retirement). If `payroll_instruction_id` is provided, "
                    "fetches that single instruction; otherwise lists all. Each entry includes "
                    "itemID values you can pass to `manage_worker_general_deduction` as `item_id`."
                ),
                coroutine=_get_worker_payroll_instructions,
                args_schema=GetPayrollInstructionsInput,
            ),
        ]

        if not self.enable_mutations:
            return tools

        async def _manage_worker_general_deduction(**kwargs: Any) -> dict[str, Any]:
            normalized = dict(kwargs)
            goal = normalized.get("deduction_goal")
            if goal is not None and hasattr(goal, "model_dump"):
                normalized["deduction_goal"] = goal.model_dump()
            action = normalized["action"]
            try:
                body = build_general_deduction_event(**normalized)
            except ValueError as err:
                return {"error": str(err), "status_code": 422}
            path = _ACTION_PATHS[action]
            return await component._post_event(conn, path=path, body=body)

        tools.append(
            StructuredTool.from_function(
                name="manage_worker_general_deduction",
                description=(
                    "Manage a worker's general-deduction instruction. Set `action='start'` to add "
                    "a new deduction (needs deduction_code, rate, optional goal), `'change'` to "
                    "update an existing one (needs item_id + deduction_code + fields to change), "
                    "or `'stop'` to end one (needs item_id). All actions need associate_oid, "
                    "payroll_file_number, payroll_agreement_id, and effective_date."
                ),
                coroutine=_manage_worker_general_deduction,
                args_schema=ManageGeneralDeductionInput,
            ),
        )

        return tools

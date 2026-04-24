"""ADPPayDataInputToolsComponent — pay-data-input submission tool for Langflow Agents.

Backs the ADP WFN `payroll/pay-data-input v1` tile. Exposes a single structured
tool that submits pay-data-input events (earnings, deductions, memos, reportable
earnings/benefits, tax-frequency overrides) for a single worker × pay-number
combination. Gated behind `enable_mutations` because pay-run modifications are
high-blast-radius.
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

PATH_MODIFY = "/events/payroll/v1/pay-data-input.modify"


def _code(code_value: str | None) -> dict[str, Any] | None:
    if code_value is None:
        return None
    return {"codeValue": code_value}


def _amount(amount_value: float, currency_code: str | None = "USD") -> dict[str, Any]:
    out: dict[str, Any] = {"amountValue": amount_value}
    if currency_code:
        out["currencyCode"] = currency_code
    return out


def _build_earning_input(item: dict[str, Any]) -> dict[str, Any]:
    earning: dict[str, Any] = {}
    if "earning_code" in item and item["earning_code"] is not None:
        earning["earningCode"] = _code(item["earning_code"])
    if item.get("number_of_hours") is not None:
        earning["numberOfHours"] = item["number_of_hours"]
    if item.get("earnings_amount") is not None:
        earning["earningsAmount"] = _amount(item["earnings_amount"], item.get("currency_code", "USD"))
    if item.get("rate_value") is not None:
        rate: dict[str, Any] = {"rateValue": item["rate_value"]}
        if item.get("currency_code"):
            rate["currencyCode"] = item["currency_code"]
        earning["rate"] = rate
    if item.get("earned_pay_period_week_number") is not None:
        earning["earnedPayPeriodWeekNumber"] = item["earned_pay_period_week_number"]
    if item.get("shift_code") is not None:
        earning["configurationTags"] = [{"tagCode": "Shift Code", "tagValues": [str(item["shift_code"])]}]
    return earning


def _build_deduction_input(item: dict[str, Any]) -> dict[str, Any]:
    deduction: dict[str, Any] = {}
    if "deduction_code" in item and item["deduction_code"] is not None:
        deduction["deductionCode"] = _code(item["deduction_code"])
    if item.get("rate_value") is not None:
        deduction["deductionRate"] = {
            "rateValue": item["rate_value"],
            "currencyCode": item.get("currency_code") or "USD",
        }
    return deduction


def _build_memo_input(item: dict[str, Any]) -> dict[str, Any]:
    memo: dict[str, Any] = {}
    if "memo_code" in item and item["memo_code"] is not None:
        memo["memoCode"] = _code(item["memo_code"])
    if item.get("amount_value") is not None:
        memo["memoAmount"] = _amount(item["amount_value"], item.get("currency_code", "USD"))
    return memo


def _build_reportable_input(item: dict[str, Any]) -> dict[str, Any]:
    reportable: dict[str, Any] = {}
    if "code" in item and item["code"] is not None:
        reportable["reportableEarningAndBenefitCode"] = _code(item["code"])
    if item.get("amount_value") is not None:
        reportable["reportableEarningAndBenefitAmount"] = _amount(
            item["amount_value"], item.get("currency_code", "USD"),
        )
    return reportable


def _build_tax_input(item: dict[str, Any]) -> dict[str, Any]:
    tax: dict[str, Any] = {}
    if "tax_cycle_code" in item and item["tax_cycle_code"] is not None:
        tax["taxCycleCode"] = _code(item["tax_cycle_code"])
    return tax


def build_pay_data_input_event(
    *,
    associate_oid: str,
    payroll_group_code: str,
    payroll_file_number: str,
    pay_number: str = "1",
    payroll_processing_job_id: str | None = None,
    modification_type: Literal["Add", "Append"] = "Add",
    cancel_automatic_pay_indicator: bool = False,
    earning_inputs: list[dict[str, Any]] | None = None,
    deduction_inputs: list[dict[str, Any]] | None = None,
    memo_inputs: list[dict[str, Any]] | None = None,
    reportable_earning_benefit_inputs: list[dict[str, Any]] | None = None,
    tax_inputs: list[dict[str, Any]] | None = None,
    additional_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pay_input: dict[str, Any] = {
        "earningInputs": [_build_earning_input(e) for e in (earning_inputs or [])],
        "deductionInputs": [_build_deduction_input(d) for d in (deduction_inputs or [])],
        "memoInputs": [_build_memo_input(m) for m in (memo_inputs or [])],
        "reportableEarningAndBenefitInputs": [
            _build_reportable_input(r) for r in (reportable_earning_benefit_inputs or [])
        ],
        "taxInputs": [_build_tax_input(t) for t in (tax_inputs or [])],
        "_modificationTypeCode": modification_type,
    }
    if cancel_automatic_pay_indicator:
        pay_input["cancelAutomaticPayIndicator"] = "true"
    if additional_fields:
        for key, value in additional_fields.items():
            pay_input[key] = value

    event_context: dict[str, Any] = {"payrollGroupCode": _code(payroll_group_code)}
    if payroll_processing_job_id:
        event_context["payrollProcessingJobID"] = payroll_processing_job_id

    return {
        "events": [
            {
                "data": {
                    "eventContext": event_context,
                    "transform": {
                        "payDataInput": {
                            "payeePayInputs": [
                                {
                                    "associateOID": associate_oid,
                                    "payNumber": pay_number,
                                    "payrollProfilePayInputs": [
                                        {
                                            "payrollFileNumber": payroll_file_number,
                                            "payInputs": [pay_input],
                                        },
                                    ],
                                },
                            ],
                        },
                    },
                },
            },
        ],
    }


class EarningInput(BaseModel):
    earning_code: str = Field(description="Earnings code (e.g. 'R' regular, 'O' overtime, 'T' tips, 'B' bonus).")
    number_of_hours: float | None = Field(default=None, description="Hours worked (for hourly earnings).")
    earnings_amount: float | None = Field(default=None, description="Flat earnings amount (for lump sums like bonus).")
    rate_value: float | None = Field(default=None, description="Per-unit rate value (e.g. hourly rate, tip rate).")
    currency_code: str = Field(default="USD", description="ISO-4217 currency code (default USD).")
    earned_pay_period_week_number: int | None = Field(
        default=None, description="Week number within a multi-week FLSA pay period (1 or 2).",
    )
    shift_code: str | None = Field(default=None, description="Shift code for premium/shift-differential pay.")


class DeductionInput(BaseModel):
    deduction_code: str = Field(description="Deduction code.")
    rate_value: float | None = Field(default=None, description="Deduction amount.")
    currency_code: str = Field(default="USD", description="ISO-4217 currency code (default USD).")


class MemoInput(BaseModel):
    memo_code: str = Field(description="Memo code (e.g. 'G.T.L.' for group term life).")
    amount_value: float | None = Field(default=None, description="Memo amount.")
    currency_code: str = Field(default="USD", description="ISO-4217 currency code (default USD).")


class ReportableEarningBenefitInput(BaseModel):
    code: str = Field(description="Reportable earning/benefit code (e.g. 'T' tips reported).")
    amount_value: float | None = Field(default=None, description="Reportable amount.")
    currency_code: str = Field(default="USD", description="ISO-4217 currency code (default USD).")


class TaxInput(BaseModel):
    tax_cycle_code: str = Field(description="Tax-cycle override code (e.g. 'B' bonus frequency).")


class SubmitPayDataInputArgs(BaseModel):
    associate_oid: str = Field(description="ADP associate OID of the worker.")
    payroll_group_code: str = Field(description="Payroll group/company code (e.g. '94N').")
    payroll_file_number: str = Field(description="Worker's payroll file number within the payroll group.")
    pay_number: str = Field(default="1", description="Pay number when a worker has multiple pay numbers (default '1').")
    payroll_processing_job_id: str | None = Field(
        default=None,
        description="Human-readable label for the pay-run job (e.g. 'Regular, OT', 'Bonus'). Optional.",
    )
    modification_type: Literal["Add", "Append"] = Field(
        default="Add",
        description="'Add' replaces existing inputs of this type; 'Append' adds alongside existing.",
    )
    cancel_automatic_pay_indicator: bool = Field(
        default=False,
        description="Skip the worker's standard automatic pay for this pay period.",
    )
    earning_inputs: list[EarningInput] = Field(
        default_factory=list, description="Earnings entries (hours, amounts, or rates).",
    )
    deduction_inputs: list[DeductionInput] = Field(
        default_factory=list, description="One-time deduction entries.",
    )
    memo_inputs: list[MemoInput] = Field(
        default_factory=list, description="Memo/informational entries.",
    )
    reportable_earning_benefit_inputs: list[ReportableEarningBenefitInput] = Field(
        default_factory=list, description="Reportable earnings/benefits (e.g. tip reporting).",
    )
    tax_inputs: list[TaxInput] = Field(
        default_factory=list, description="Tax-cycle overrides (e.g. bonus tax frequency).",
    )
    additional_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Escape hatch: extra fields merged into the pay-input entry for rare payload shapes.",
    )


class ADPPayDataInputToolsComponent(Component):
    display_name = "ADP Pay Data Input Tools"
    description = (
        "Agent tool for submitting ADP WFN pay-data-input events: earnings, deductions, "
        "memos, reportable earnings/benefits, and tax-frequency overrides for a single "
        "worker × pay number. Gated behind `enable_mutations` — turn on only when the "
        "flow is meant to modify payroll."
    )
    icon = "CircleDollarSign"
    name = "ADPPayDataInputTools"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release — single agent tool `submit_pay_data_input` backing ADP WFN "
                "`payroll/pay-data-input v1`. Supports earnings, deductions, memos, reportable "
                "earnings/benefits, and tax-cycle overrides with Add/Append modification types. "
                "Gated behind the `enable_mutations` input (default off)."
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
                "Expose the pay-data-input submission tool to the agent. Off by default — "
                "pay-run modifications are high-blast-radius. Turn on only when the flow is "
                "meant to act on payroll data."
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
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
        timeout: float,
    ) -> httpx.Response:
        return await client.request(
            method="POST",
            url=url,
            headers=headers,
            json=json_body,
            timeout=timeout,
        )

    async def _post_event(self, conn: ADPConnection, *, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{conn.api_base_url}{path}"
        validate_adp_url(url, field_name="api_base_url")
        headers = {"Authorization": f"Bearer {conn.access_token}"}

        async with build_mtls_httpx_client(conn, timeout=30.0) as client:
            response = await self._execute_request(client, url=url, headers=headers, json_body=body, timeout=30.0)

            if response.status_code == HTTP_UNAUTHORIZED:
                await fetch_token(conn, force=True)
                headers["Authorization"] = f"Bearer {conn.access_token}"
                response = await self._execute_request(
                    client, url=url, headers=headers, json_body=body, timeout=30.0,
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

    async def build_tools(self) -> list[Tool]:
        if not self.enable_mutations:
            return []

        conn: ADPConnection = self.connection
        component = self

        async def _submit_pay_data_input(**kwargs: Any) -> dict[str, Any]:
            # Pydantic models arrive as dicts via StructuredTool — normalize all list items.
            normalized = dict(kwargs)
            for key in (
                "earning_inputs",
                "deduction_inputs",
                "memo_inputs",
                "reportable_earning_benefit_inputs",
                "tax_inputs",
            ):
                items = normalized.get(key) or []
                normalized[key] = [item.model_dump() if hasattr(item, "model_dump") else item for item in items]
            body = build_pay_data_input_event(**normalized)
            return await component._post_event(conn, path=PATH_MODIFY, body=body)

        return [
            StructuredTool.from_function(
                name="submit_pay_data_input",
                description=(
                    "Submit a pay-data-input modification for a single worker and pay number: "
                    "add/append earnings (hours, amounts, rates), deductions, memos, reportable "
                    "earnings/benefits, and tax-cycle overrides. Requires the worker's associate OID, "
                    "payroll group code, and payroll file number. Use `modification_type='Add'` to "
                    "replace existing inputs of this type, `'Append'` to add alongside. Returns the "
                    "ADP event response."
                ),
                coroutine=_submit_pay_data_input,
                args_schema=SubmitPayDataInputArgs,
            ),
        ]

"""ADP worker compensation tools — compensation-change tools for Langflow Agents.

Backs the ADP WFN `workers-compensation-management v2` tile. All operations are
mutations (event POSTs); reads live on the Workers v2 tile. Mutations are
hidden behind an `enable_mutations` opt-in because salary changes and bonus
add/remove are high-blast-radius.
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
    fetch_token,
    validate_adp_url,
)
from lfx.field_typing import Tool  # noqa: TC001 — runtime return annotation used by LangFlow registry

# ---------------------------------------------------------------------------
# Backward-compat stub — orchestrator will update __init__.py later.


PATH_ADD_ADDITIONAL = "/events/hr/v1/worker.work-assignment.additional-remuneration.add"
PATH_CHANGE_ADDITIONAL = "/events/hr/v1/worker.work-assignment.additional-remuneration.change"
PATH_REMOVE_ADDITIONAL = "/events/hr/v1/worker.work-assignment.additional-remuneration.remove"
PATH_CHANGE_BASE = "/events/hr/v1/worker.work-assignment.base-remuneration.change"


def _worker_context(associate_oid: str, work_assignment_item_id: str) -> dict[str, Any]:
    return {
        "associateOID": associate_oid,
        "workAssignment": {"itemID": work_assignment_item_id},
    }


def _currency_amount(amount: float, currency: str) -> dict[str, Any]:
    return {"amountValue": amount, "currencyCode": currency}


def build_change_base_pay_event(
    *,
    associate_oid: str,
    work_assignment_item_id: str,
    new_annual_amount: float,
    currency_code: str = "USD",
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    work_assignment: dict[str, Any] = {
        "baseRemuneration": {"annualRateAmount": _currency_amount(new_annual_amount, currency_code)},
    }
    if effective_date:
        work_assignment["baseRemuneration"]["effectiveDate"] = effective_date
    transform: dict[str, Any] = {"workAssignment": work_assignment}
    if effective_date:
        transform["effectiveDateTime"] = effective_date
    if reason_code:
        transform["eventReasonCode"] = {"codeValue": reason_code}
    return {
        "events": [
            {
                "data": {
                    "eventContext": {"worker": _worker_context(associate_oid, work_assignment_item_id)},
                    "transform": transform,
                },
            },
        ],
    }


def build_add_additional_remuneration_event(
    *,
    associate_oid: str,
    work_assignment_item_id: str,
    name_code: str,
    rate_amount: float,
    currency_code: str = "USD",
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    additional: dict[str, Any] = {
        "nameCode": {"codeValue": name_code},
        "rate": {"rateAmount": _currency_amount(rate_amount, currency_code)},
    }
    if effective_date:
        additional["effectiveDate"] = effective_date
    transform: dict[str, Any] = {"workAssignment": {"additionalRemunerations": [additional]}}
    if effective_date:
        transform["effectiveDateTime"] = effective_date
    if reason_code:
        transform["eventReasonCode"] = {"codeValue": reason_code}
    return {
        "events": [
            {
                "data": {
                    "eventContext": {"worker": _worker_context(associate_oid, work_assignment_item_id)},
                    "transform": transform,
                },
            },
        ],
    }


def build_change_additional_remuneration_event(
    *,
    associate_oid: str,
    work_assignment_item_id: str,
    additional_remuneration_item_id: str,
    rate_amount: float | None = None,
    currency_code: str = "USD",
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    additional: dict[str, Any] = {"itemID": additional_remuneration_item_id}
    if rate_amount is not None:
        additional["rate"] = {"rateAmount": _currency_amount(rate_amount, currency_code)}
    if effective_date:
        additional["effectiveDate"] = effective_date
    transform: dict[str, Any] = {"workAssignment": {"additionalRemunerations": [additional]}}
    if effective_date:
        transform["effectiveDateTime"] = effective_date
    if reason_code:
        transform["eventReasonCode"] = {"codeValue": reason_code}
    return {
        "events": [
            {
                "data": {
                    "eventContext": {"worker": _worker_context(associate_oid, work_assignment_item_id)},
                    "transform": transform,
                },
            },
        ],
    }


def build_remove_additional_remuneration_event(
    *,
    associate_oid: str,
    work_assignment_item_id: str,
    additional_remuneration_item_id: str,
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    transform: dict[str, Any] = {
        "workAssignment": {
            "additionalRemunerations": [{"itemID": additional_remuneration_item_id}],
        },
    }
    if effective_date:
        transform["effectiveDateTime"] = effective_date
    if reason_code:
        transform["eventReasonCode"] = {"codeValue": reason_code}
    return {
        "events": [
            {
                "data": {
                    "eventContext": {"worker": _worker_context(associate_oid, work_assignment_item_id)},
                    "transform": transform,
                },
            },
        ],
    }


class ChangeBasePayInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID of the employee")
    work_assignment_item_id: str = Field(
        description="Item ID of the work assignment to update (from workAssignments[].itemID).",
    )
    new_annual_amount: float = Field(description="New annual base pay amount")
    currency_code: str = Field(default="USD", description="ISO-4217 currency code (default USD)")
    effective_date: str | None = Field(
        default=None,
        description="ISO-8601 effective date (YYYY-MM-DD). If omitted, ADP defaults to today.",
    )
    reason_code: str | None = Field(
        default=None,
        description="ADP event reason code (e.g. 'Annual Review', 'Promotion'). Optional.",
    )


class AddAdditionalRemunerationInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID of the employee")
    work_assignment_item_id: str = Field(description="Item ID of the work assignment to update.")
    name_code: str = Field(description="Type of compensation, e.g. 'Bonus', 'Commission', 'Allowance'.")
    rate_amount: float = Field(description="Amount of the additional remuneration")
    currency_code: str = Field(default="USD", description="ISO-4217 currency code (default USD)")
    effective_date: str | None = Field(default=None, description="ISO-8601 effective date (YYYY-MM-DD).")
    reason_code: str | None = Field(default=None, description="ADP event reason code. Optional.")


class ChangeAdditionalRemunerationInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID of the employee")
    work_assignment_item_id: str = Field(description="Item ID of the work assignment.")
    additional_remuneration_item_id: str = Field(
        description="Item ID of the specific additional-remuneration entry to change.",
    )
    rate_amount: float | None = Field(default=None, description="New amount. Omit to keep unchanged.")
    currency_code: str = Field(default="USD", description="ISO-4217 currency code (default USD)")
    effective_date: str | None = Field(default=None, description="ISO-8601 effective date (YYYY-MM-DD).")
    reason_code: str | None = Field(default=None, description="ADP event reason code. Optional.")


class RemoveAdditionalRemunerationInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID of the employee")
    work_assignment_item_id: str = Field(description="Item ID of the work assignment.")
    additional_remuneration_item_id: str = Field(
        description="Item ID of the additional-remuneration entry to remove.",
    )
    effective_date: str | None = Field(default=None, description="ISO-8601 effective date.")
    reason_code: str | None = Field(default=None, description="ADP event reason code. Optional.")


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


def build_worker_compensation_tools(
    connection: ADPConnection,
    request_cache: RequestCache,  # accepted for registry uniformity; unused for writes  # noqa: ARG001
) -> list[Tool]:
    conn = connection

    async def _change_employee_base_pay(**kwargs: Any) -> dict[str, Any]:
        body = build_change_base_pay_event(**kwargs)
        return await _post_event(conn, path=PATH_CHANGE_BASE, body=body)

    async def _add_employee_additional_remuneration(**kwargs: Any) -> dict[str, Any]:
        body = build_add_additional_remuneration_event(**kwargs)
        return await _post_event(conn, path=PATH_ADD_ADDITIONAL, body=body)

    async def _change_employee_additional_remuneration(**kwargs: Any) -> dict[str, Any]:
        body = build_change_additional_remuneration_event(**kwargs)
        return await _post_event(conn, path=PATH_CHANGE_ADDITIONAL, body=body)

    async def _remove_employee_additional_remuneration(**kwargs: Any) -> dict[str, Any]:
        body = build_remove_additional_remuneration_event(**kwargs)
        return await _post_event(conn, path=PATH_REMOVE_ADDITIONAL, body=body)

    return [
        StructuredTool.from_function(
            name="change_employee_base_pay",
            description=(
                "Change an employee's base (salary) pay. Requires the employee's associate OID "
                "and the specific work assignment's item ID. Returns the ADP event response."
            ),
            coroutine=_change_employee_base_pay,
            args_schema=ChangeBasePayInput,
        ),
        StructuredTool.from_function(
            name="add_employee_additional_remuneration",
            description=(
                "Add an additional remuneration (bonus, allowance, commission) to an employee's "
                "work assignment. Use `name_code` to specify the type (e.g. 'Bonus')."
            ),
            coroutine=_add_employee_additional_remuneration,
            args_schema=AddAdditionalRemunerationInput,
        ),
        StructuredTool.from_function(
            name="change_employee_additional_remuneration",
            description=(
                "Change an existing additional-remuneration entry on an employee's work "
                "assignment. Requires both the work-assignment itemID and the specific "
                "additional-remuneration entry's itemID."
            ),
            coroutine=_change_employee_additional_remuneration,
            args_schema=ChangeAdditionalRemunerationInput,
        ),
        StructuredTool.from_function(
            name="remove_employee_additional_remuneration",
            description=(
                "Remove an additional-remuneration entry from an employee's work assignment."
            ),
            coroutine=_remove_employee_additional_remuneration,
            args_schema=RemoveAdditionalRemunerationInput,
        ),
    ]

"""ADP worker HR profiles tools — worker-profile reads + targeted writes.

Backs the ADP WFN `hr-worker-profiles v1` tile. Exposes two reads (additional
remunerations, reportable benefits) plus four mutations that don't already
exist via the events API: corporate-group create, primary-assignment set,
reportable-benefit create/update.

Deliberately omits:
- additional-remunerations POST/PUT and base-remuneration PUT, which duplicate
  the event-API tools in `adp_worker_compensation_tools.py`.
- worker-dates PUT — request schema was not captured during spec harvest;
  deferred as a follow-up.
- the 4 /meta discovery GETs — shapes differ per resource, so a single
  consolidated tool would be misleading.
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
# ---------------------------------------------------------------------------
class ADPWorkerHrProfilesToolsComponent:
    """Deprecated stub — use build_worker_hr_profiles_tools instead."""


_BASE = "/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment_id}"
PATH_ADDITIONAL_REMUNERATIONS = _BASE + "/additional-remunerations"
PATH_REPORTABLE_BENEFITS = _BASE + "/reportable-benefits"
PATH_CORPORATE_GROUPS = _BASE + "/corporate-groups"
PATH_PRIMARY_ASSIGNMENT = _BASE + "/primary-assignment"


def _deep_merge(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst


def _code(value: str | None) -> dict[str, Any] | None:
    return {"codeValue": value} if value else None


def _currency_amount(amount: float, currency: str) -> dict[str, Any]:
    return {"amount": amount, "currencyCode": currency}


# ---------- Read extractors ----------


def extract_additional_remunerations(payload: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for rem in payload.get("additionalRemunerations") or []:
        rate_obj = rem.get("remunerationRate") or {}
        rate_amount = rate_obj.get("rate") or {}
        rows.append({
            "remunerationID": rem.get("remunerationID"),
            "nameCode": (rem.get("nameCode") or {}).get("codeValue"),
            "remunerationTypeCode": (rem.get("remunerationTypeCode") or {}).get("codeValue"),
            "intervalCode": (rem.get("intervalCode") or {}).get("codeValue"),
            "rate": rate_amount.get("amount"),
            "currencyCode": rate_amount.get("currencyCode"),
            "effectiveDate": rem.get("effectiveDate"),
            "inactive": (rem.get("inactiveIndicator") or {}).get("indicatorValue"),
        })
    return {
        "associateOID": payload.get("associateOID"),
        "workerID": (payload.get("workerID") or {}).get("idValue"),
        "workAssignmentID": payload.get("workAssignmentID"),
        "additionalRemunerations": rows,
    }


def extract_reportable_benefits(payload: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for rb in payload.get("reportableBenefits") or []:
        amount_obj = rb.get("earningAmount") or {}
        rows.append({
            "earningID": rb.get("earningID"),
            "earningCode": (rb.get("earningCode") or {}).get("codeValue"),
            "amount": amount_obj.get("amount"),
            "currencyCode": amount_obj.get("currencyCode"),
            "itemCategoryCode": (rb.get("itemCategoryCode") or {}).get("codeValue"),
            "inactive": (rb.get("inactiveIndicator") or {}).get("indicatorValue"),
            "effectiveDate": rb.get("effectiveDate"),
        })
    return {
        "associateOID": payload.get("associateOID"),
        "workerID": (payload.get("workerID") or {}).get("idValue"),
        "workAssignmentID": payload.get("workAssignmentID"),
        "reportableBenefits": rows,
    }


# ---------- Request body builders ----------


def build_corporate_group_body(
    *,
    home_location_name: str | None = None,
    department_name: str | None = None,
    worker_group_type: str | None = None,
    worker_group_name: str | None = None,
    effective_date: str | None = None,
    status_code: str | None = None,
    additional_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if status_code or effective_date:
        group_status: dict[str, Any] = {}
        if status_code:
            group_status["statusCode"] = {"codeValue": status_code}
        if effective_date:
            group_status["effectiveDateTime"] = effective_date
        body["groupStatus"] = group_status
    if home_location_name:
        body["homeWorkLocation"] = {"nameCode": {"codeValue": home_location_name}}
    if department_name:
        body["homeOrganizationalUnits"] = [
            {"typeCode": {"codeValue": "Department"}, "nameCode": {"codeValue": department_name}},
        ]
    if worker_group_type and worker_group_name:
        body["workerGroups"] = [
            {
                "nameCode": {"codeValue": worker_group_type},
                "groupCode": {"codeValue": worker_group_name},
            },
        ]
    if additional_fields:
        _deep_merge(body, additional_fields)
    return body


def build_primary_assignment_body(
    *,
    work_assignment_id: str,
    effective_date: str,
) -> dict[str, Any]:
    return {
        "effectiveDate": effective_date,
        "workAssignments": [
            {"workAssignmentID": work_assignment_id, "primaryIndicator": {"indicatorValue": True}},
        ],
    }


def build_reportable_benefit_body(
    *,
    earning_code: str,
    amount: float,
    currency_code: str = "USD",
    item_category_code: str | None = None,
    effective_date: str | None = None,
    earning_id: str | None = None,
    inactive: bool | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "earningCode": {"codeValue": earning_code},
        "earningAmount": _currency_amount(amount, currency_code),
    }
    if item_category_code:
        entry["itemCategoryCode"] = {"codeValue": item_category_code}
    if effective_date:
        entry["effectiveDate"] = effective_date
    if earning_id:
        entry["earningID"] = earning_id
    if inactive is not None:
        entry["inactiveIndicator"] = {"indicatorValue": inactive}
    return {"reportableBenefits": [entry]}


# ---------- Tool arg schemas ----------


class WorkAssignmentReadInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID of the employee.")
    work_assignment_id: str = Field(description="Item ID of the work assignment.")


class CreateCorporateGroupInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID of the employee.")
    work_assignment_id: str = Field(description="Item ID of the work assignment.")
    home_location_name: str | None = Field(
        default=None, description="Home work-location name (e.g. 'HQ', 'Chicago Office').",
    )
    department_name: str | None = Field(
        default=None, description="Home department name (creates a Department organizational unit).",
    )
    worker_group_type: str | None = Field(
        default=None, description="Worker-group type name, e.g. 'Cost Center'. Required with worker_group_name.",
    )
    worker_group_name: str | None = Field(
        default=None, description="Worker-group code/name, e.g. 'CC-1001'. Required with worker_group_type.",
    )
    status_code: str | None = Field(default=None, description="Group status code (e.g. 'Active').")
    effective_date: str | None = Field(default=None, description="Group effective date/time (YYYY-MM-DD).")
    additional_fields: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Escape hatch: ADP-shaped corporate-group fields merged into the request body "
            "(e.g. laborUnion, bargainingUnit, extra homeOrganizationalUnits)."
        ),
    )


class SetPrimaryAssignmentInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID of the employee.")
    work_assignment_id: str = Field(description="Item ID of the work assignment to mark as primary.")
    effective_date: str = Field(description="Effective date for the primary-assignment change (YYYY-MM-DD).")


class CreateReportableBenefitInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID of the employee.")
    work_assignment_id: str = Field(description="Item ID of the work assignment.")
    earning_code: str = Field(description="Payroll earning code, e.g. 'Reportable Tips', 'GTL'.")
    amount: float = Field(description="Reportable amount per pay period.")
    currency_code: str = Field(default="USD", description="ISO-4217 currency code.")
    item_category_code: str | None = Field(
        default=None, description="Category, e.g. 'Benefit', 'Earning'. Optional.",
    )
    effective_date: str | None = Field(default=None, description="Effective date (YYYY-MM-DD). Optional.")


class UpdateReportableBenefitInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID of the employee.")
    work_assignment_id: str = Field(description="Item ID of the work assignment.")
    earning_id: str = Field(description="ID of the reportable benefit to update (from read_worker_reportable_benefits).")  # noqa: E501
    earning_code: str | None = Field(default=None, description="Updated earning code. Omit to keep unchanged.")
    amount: float | None = Field(default=None, description="Updated amount. Omit to keep unchanged.")
    currency_code: str = Field(default="USD", description="ISO-4217 currency code (used when amount is set).")
    item_category_code: str | None = Field(default=None, description="Updated category.")
    effective_date: str | None = Field(default=None, description="Updated effective date.")
    inactive: bool | None = Field(
        default=None, description="Set True to mark the benefit inactive (effective ADP delete).",
    )


# ---------- HTTP helpers ----------


async def _call(
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
        response = await client.request(
            method=method, url=url, headers=headers, json=body, timeout=30.0,
        )
        if response.status_code == HTTP_UNAUTHORIZED:
            await fetch_token(conn, force=True)
            headers["Authorization"] = f"Bearer {conn.access_token}"
            response = await client.request(
                method=method, url=url, headers=headers, json=body, timeout=30.0,
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


def build_worker_hr_profiles_tools(
    connection: ADPConnection,
    request_cache: RequestCache,  # accepted for registry uniformity; reads don't use shared cache  # noqa: ARG001
) -> list[Tool]:
    conn = connection

    async def _read_additional_remunerations(
        associate_oid: str, work_assignment_id: str,
    ) -> dict[str, Any]:
        path = PATH_ADDITIONAL_REMUNERATIONS.format(aoid=associate_oid, assignment_id=work_assignment_id)
        result = await _call(conn, method="GET", path=path)
        if "error" in result:
            return result
        return extract_additional_remunerations(result)

    async def _read_reportable_benefits(
        associate_oid: str, work_assignment_id: str,
    ) -> dict[str, Any]:
        path = PATH_REPORTABLE_BENEFITS.format(aoid=associate_oid, assignment_id=work_assignment_id)
        result = await _call(conn, method="GET", path=path)
        if "error" in result:
            return result
        return extract_reportable_benefits(result)

    async def _create_corporate_group(
        associate_oid: str, work_assignment_id: str, **kw: Any,
    ) -> dict[str, Any]:
        path = PATH_CORPORATE_GROUPS.format(aoid=associate_oid, assignment_id=work_assignment_id)
        body = build_corporate_group_body(**kw)
        return await _call(conn, method="POST", path=path, body=body)

    async def _set_primary_assignment(
        associate_oid: str, work_assignment_id: str, effective_date: str,
    ) -> dict[str, Any]:
        path = PATH_PRIMARY_ASSIGNMENT.format(aoid=associate_oid, assignment_id=work_assignment_id)
        body = build_primary_assignment_body(
            work_assignment_id=work_assignment_id, effective_date=effective_date,
        )
        return await _call(conn, method="PUT", path=path, body=body)

    async def _create_reportable_benefit(
        associate_oid: str, work_assignment_id: str, **kw: Any,
    ) -> dict[str, Any]:
        path = PATH_REPORTABLE_BENEFITS.format(aoid=associate_oid, assignment_id=work_assignment_id)
        body = build_reportable_benefit_body(**kw)
        return await _call(conn, method="POST", path=path, body=body)

    async def _update_reportable_benefit(
        associate_oid: str, work_assignment_id: str, earning_id: str, **kw: Any,
    ) -> dict[str, Any]:
        path = PATH_REPORTABLE_BENEFITS.format(aoid=associate_oid, assignment_id=work_assignment_id)
        kw_amount = kw.get("amount")
        kw_earning_code = kw.get("earning_code")
        # Build entry with only supplied fields + the required earning_id
        body = build_reportable_benefit_body(
            earning_code=kw_earning_code or "",
            amount=kw_amount if kw_amount is not None else 0.0,
            currency_code=kw.get("currency_code", "USD"),
            item_category_code=kw.get("item_category_code"),
            effective_date=kw.get("effective_date"),
            earning_id=earning_id,
            inactive=kw.get("inactive"),
        )
        # Strip defaulted stand-ins for fields the caller didn't supply
        entry = body["reportableBenefits"][0]
        if kw_earning_code is None:
            entry.pop("earningCode", None)
        if kw_amount is None:
            entry.pop("earningAmount", None)
        return await _call(conn, method="PUT", path=path, body=body)

    return [
        StructuredTool.from_function(
            name="read_worker_additional_remunerations",
            description=(
                "Read an employee's additional remunerations on a work assignment (bonuses, "
                "allowances, commissions). Returns a flat list with remunerationID (pass to "
                "compensation-tile tools as `additional_remuneration_item_id`), name, type, "
                "rate, currency, effective date, and inactive flag."
            ),
            coroutine=_read_additional_remunerations,
            args_schema=WorkAssignmentReadInput,
        ),
        StructuredTool.from_function(
            name="read_worker_reportable_benefits",
            description=(
                "Read an employee's reportable benefits on a work assignment (GTL, reportable "
                "tips, etc.). Returns a flat list with earningID (pass to update/inactivate), "
                "earning code, amount, currency, category, and effective date."
            ),
            coroutine=_read_reportable_benefits,
            args_schema=WorkAssignmentReadInput,
        ),
        StructuredTool.from_function(
            name="create_worker_corporate_group",
            description=(
                "Attach a corporate group (home location, department, worker group) to an "
                "employee's work assignment. Use `additional_fields` for laborUnion, "
                "bargainingUnit, or additional organizational units."
            ),
            coroutine=_create_corporate_group,
            args_schema=CreateCorporateGroupInput,
        ),
        StructuredTool.from_function(
            name="set_worker_primary_assignment",
            description=(
                "Mark a work assignment as the employee's primary assignment. Use when the "
                "employee has multiple active assignments and the primary one needs to change."
            ),
            coroutine=_set_primary_assignment,
            args_schema=SetPrimaryAssignmentInput,
        ),
        StructuredTool.from_function(
            name="create_worker_reportable_benefit",
            description=(
                "Add a reportable benefit (e.g. GTL, reportable tips) to an employee's work "
                "assignment. Specify earning_code and amount; returns the ADP response."
            ),
            coroutine=_create_reportable_benefit,
            args_schema=CreateReportableBenefitInput,
        ),
        StructuredTool.from_function(
            name="update_worker_reportable_benefit",
            description=(
                "Update an existing reportable benefit on a work assignment by earning_id. "
                "Only supplied fields are sent. Set `inactive=True` to deactivate (ADP-delete)."
            ),
            coroutine=_update_reportable_benefit,
            args_schema=UpdateReportableBenefitInput,
        ),
    ]

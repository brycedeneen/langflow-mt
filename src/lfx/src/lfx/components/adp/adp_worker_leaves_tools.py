"""ADP worker leaves tools — worker-leaves read + event tools.

Backs the ADP WFN `worker-leaves v2` tile. Exposes a list-leaves read plus the
four leave-event POSTs (request absence, change, cancel, return from leave),
with the four `/meta` discovery endpoints consolidated into a single tool.
"""

from __future__ import annotations

from typing import Any, Literal

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


PATH_LIST_LEAVES = "/hr/v2/workers/{aoid}/leaves"
PATH_ABSENCE_REQUEST = "/events/hr/v1/worker.leave.absence.request"
PATH_ABSENCE_REQUEST_META = "/events/hr/v1/worker.leave.absence.request/meta"
PATH_LEAVE_CANCEL = "/events/hr/v1/worker.leave.cancel"
PATH_LEAVE_CANCEL_META = "/events/hr/v1/worker.leave.cancel/meta"
PATH_LEAVE_CHANGE = "/events/hr/v1/worker.leave.change"
PATH_LEAVE_CHANGE_META = "/events/hr/v1/worker.leave.change/meta"
PATH_LEAVE_RETURN_REQUEST = "/events/hr/v1/worker.leave.return.request"
PATH_LEAVE_RETURN_REQUEST_META = "/events/hr/v1/worker.leave.return.request/meta"

_META_OPERATIONS = {
    "absence_request": PATH_ABSENCE_REQUEST_META,
    "cancel": PATH_LEAVE_CANCEL_META,
    "change": PATH_LEAVE_CHANGE_META,
    "return_request": PATH_LEAVE_RETURN_REQUEST_META,
}


# ---------- Read: extractor for GET /hr/v2/workers/{aoid}/leaves ----------


def _leave_absence_summary(la: dict[str, Any] | None) -> dict[str, Any] | None:
    if not la:
        return None
    status = la.get("leaveStatus") or {}
    status_code = status.get("statusCode") or {}
    return {
        "leaveTypeCode": (la.get("leaveTypeCode") or {}).get("codeValue"),
        "leaveSubTypeCode": (la.get("leaveSubTypeCode") or {}).get("codeValue"),
        "startDateTime": la.get("startDateTime"),
        "expectedEndDateTime": la.get("expectedEndDateTime"),
        "leaveDuration": (la.get("leaveDuration") or {}).get("quantityValue"),
        "paymentStatusCode": (la.get("paymentStatusCode") or {}).get("codeValue"),
        "statutoryFilingIndicator": (la.get("statutoryFilingIndicator") or {}).get("indicatorValue"),
        "statutoryTypeCode": (la.get("statutoryTypeCode") or {}).get("codeValue"),
        "leaveStatus": status_code.get("codeValue") if isinstance(status_code, dict) else None,
    }


def _leave_return_summary(lr: dict[str, Any] | None) -> dict[str, Any] | None:
    if not lr:
        return None
    status = lr.get("returnStatus") or {}
    status_code = status.get("statusCode") or {}
    return {
        "returnDateTime": lr.get("returnDateTime"),
        "notificationReceivedDateTime": lr.get("notificationReceivedDateTime"),
        "returnToWorkIndicator": (lr.get("returnToWorkIndicator") or {}).get("indicatorValue"),
        "returnStatus": status_code.get("codeValue") if isinstance(status_code, dict) else None,
    }


def extract_worker_leaves(worker_leaves: list[dict[str, Any]]) -> dict[str, Any]:
    """Flatten the `workerLeaves[]` response into an agent-friendly list.

    Each worker in the response carries a `leaves[]` array; we emit one entry
    per leave (preserving the worker/assignment keys on each) so an agent can
    reason about a single row at a time.
    """
    rows: list[dict[str, Any]] = [
        {
            "associateOID": wl.get("associateOID"),
            "workerID": (wl.get("workerID") or {}).get("idValue"),
            "workAssignmentID": wl.get("workAssignmentID"),
            "itemID": leaf.get("itemID"),
            "effectiveDateTime": leaf.get("effectiveDateTime"),
            "leaveAbsence": _leave_absence_summary(leaf.get("leaveAbsence")),
            "leaveReturn": _leave_return_summary(leaf.get("leaveReturn")),
        }
        for wl in (worker_leaves or [])
        for leaf in (wl.get("leaves") or [])
    ]
    return {"leaves": rows}


# ---------- Event envelope builders ----------


def _event_context(
    *,
    associate_oid: str,
    work_assignment_id: str | None,
    leave_id: str | None,
) -> dict[str, Any]:
    ctx: dict[str, Any] = {"associateOID": associate_oid}
    if work_assignment_id:
        ctx["workAssignmentID"] = work_assignment_id
    if leave_id:
        ctx["leaveID"] = leave_id
    return ctx


def _wrap_event(event_context: dict[str, Any], transform: dict[str, Any]) -> dict[str, Any]:
    return {"events": [{"data": {"eventContext": event_context, "transform": transform}}]}


def _base_transform(
    *,
    effective_date: str | None,
    reason_code: str | None,
) -> dict[str, Any]:
    transform: dict[str, Any] = {}
    if effective_date:
        transform["effectiveDateTime"] = effective_date
    if reason_code:
        transform["eventReasonCode"] = {"codeValue": reason_code}
    return transform


def _leave_absence_payload(
    *,
    start_date: str | None,
    expected_end_date: str | None,
    leave_type_code: str | None,
    leave_sub_type_code: str | None,
    payment_status_code: str | None,
    statutory_filing_indicator: bool | None,
    statutory_type_code: str | None,
    leave_duration: float | None,
    comment: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if start_date:
        payload["startDateTime"] = start_date
    if expected_end_date:
        payload["expectedEndDateTime"] = expected_end_date
    if leave_type_code:
        payload["leaveTypeCode"] = {"codeValue": leave_type_code}
    if leave_sub_type_code:
        payload["leaveSubTypeCode"] = {"codeValue": leave_sub_type_code}
    if payment_status_code:
        payload["paymentStatusCode"] = {"codeValue": payment_status_code}
    if statutory_filing_indicator is not None:
        payload["statutoryFilingIndicator"] = {"indicatorValue": statutory_filing_indicator}
    if statutory_type_code:
        payload["statutoryTypeCode"] = {"codeValue": statutory_type_code}
    if leave_duration is not None:
        payload["leaveDuration"] = {"quantityValue": leave_duration}
    if comment:
        payload["comment"] = {"noteText": comment}
    return payload


def _leave_return_payload(
    *,
    return_date: str | None,
    return_to_work_indicator: bool | None,
    notification_received_date: str | None,
    comment: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if return_date:
        payload["returnDateTime"] = return_date
    if return_to_work_indicator is not None:
        payload["returnToWorkIndicator"] = {"indicatorValue": return_to_work_indicator}
    if notification_received_date:
        payload["notificationReceivedDateTime"] = notification_received_date
    if comment:
        payload["comment"] = {"noteText": comment}
    return payload


def build_request_leave_absence_event(
    *,
    associate_oid: str,
    start_date: str,
    expected_end_date: str | None = None,
    leave_type_code: str | None = None,
    leave_sub_type_code: str | None = None,
    payment_status_code: str | None = None,
    statutory_filing_indicator: bool | None = None,
    statutory_type_code: str | None = None,
    leave_duration: float | None = None,
    comment: str | None = None,
    work_assignment_id: str | None = None,
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    absence = _leave_absence_payload(
        start_date=start_date,
        expected_end_date=expected_end_date,
        leave_type_code=leave_type_code,
        leave_sub_type_code=leave_sub_type_code,
        payment_status_code=payment_status_code,
        statutory_filing_indicator=statutory_filing_indicator,
        statutory_type_code=statutory_type_code,
        leave_duration=leave_duration,
        comment=comment,
    )
    transform = _base_transform(effective_date=effective_date or start_date, reason_code=reason_code)
    transform["workerLeave"] = {"leaveAbsence": absence}
    return _wrap_event(
        _event_context(associate_oid=associate_oid, work_assignment_id=work_assignment_id, leave_id=None),
        transform,
    )


def build_change_leave_event(
    *,
    associate_oid: str,
    leave_id: str,
    effective_date: str,
    start_date: str | None = None,
    expected_end_date: str | None = None,
    leave_type_code: str | None = None,
    leave_sub_type_code: str | None = None,
    payment_status_code: str | None = None,
    return_date: str | None = None,
    return_to_work_indicator: bool | None = None,
    comment: str | None = None,
    work_assignment_id: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    transform = _base_transform(effective_date=effective_date, reason_code=reason_code)
    worker_leave: dict[str, Any] = {}
    absence = _leave_absence_payload(
        start_date=start_date,
        expected_end_date=expected_end_date,
        leave_type_code=leave_type_code,
        leave_sub_type_code=leave_sub_type_code,
        payment_status_code=payment_status_code,
        statutory_filing_indicator=None,
        statutory_type_code=None,
        leave_duration=None,
        comment=comment,
    )
    if absence:
        worker_leave["leaveAbsence"] = absence
    leave_return = _leave_return_payload(
        return_date=return_date,
        return_to_work_indicator=return_to_work_indicator,
        notification_received_date=None,
        comment=None,
    )
    if leave_return:
        worker_leave["leaveReturn"] = leave_return
    if worker_leave:
        transform["workerLeave"] = worker_leave
    return _wrap_event(
        _event_context(associate_oid=associate_oid, work_assignment_id=work_assignment_id, leave_id=leave_id),
        transform,
    )


def build_cancel_leave_event(
    *,
    associate_oid: str,
    leave_id: str,
    effective_date: str,
    work_assignment_id: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    transform = _base_transform(effective_date=effective_date, reason_code=reason_code)
    return _wrap_event(
        _event_context(associate_oid=associate_oid, work_assignment_id=work_assignment_id, leave_id=leave_id),
        transform,
    )


def build_request_leave_return_event(
    *,
    associate_oid: str,
    leave_id: str,
    return_date: str,
    return_to_work_indicator: bool = True,
    notification_received_date: str | None = None,
    comment: str | None = None,
    work_assignment_id: str | None = None,
    effective_date: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    transform = _base_transform(effective_date=effective_date or return_date, reason_code=reason_code)
    transform["leaveReturn"] = _leave_return_payload(
        return_date=return_date,
        return_to_work_indicator=return_to_work_indicator,
        notification_received_date=notification_received_date,
        comment=comment,
    )
    return _wrap_event(
        _event_context(associate_oid=associate_oid, work_assignment_id=work_assignment_id, leave_id=leave_id),
        transform,
    )


# ---------- Tool arg schemas ----------


class ListWorkerLeavesInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID of the employee.")
    filter: str | None = Field(
        default=None,
        description=(
            "Optional OData-style $filter expression (e.g. "
            "\"leaveAbsence/leaveStatus/statusCode/codeValue eq 'Active'\"). "
            "Forwarded to ADP as the `$filter` query parameter."
        ),
    )


class GetLeaveEventMetaInput(BaseModel):
    operation: Literal["absence_request", "cancel", "change", "return_request"] = Field(
        description=(
            "Which leave-event's meta schema to fetch. Consolidates the 4 /meta "
            "discovery endpoints."
        ),
    )
    filter: str | None = Field(default=None, description="Optional $filter forwarded to ADP.")


class RequestLeaveAbsenceInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID of the employee.")
    start_date: str = Field(description="Leave start date/time (YYYY-MM-DD).")
    expected_end_date: str | None = Field(default=None, description="Expected return date (YYYY-MM-DD).")
    leave_type_code: str | None = Field(
        default=None, description="Type of leave (e.g. 'FMLA', 'Parental', 'Personal').",
    )
    leave_sub_type_code: str | None = Field(default=None, description="Sub-type of leave.")
    payment_status_code: str | None = Field(
        default=None, description="Whether the leave is paid or unpaid (e.g. 'Paid', 'Unpaid').",
    )
    statutory_filing_indicator: bool | None = Field(
        default=None, description="True if the leave is covered by statutory rules (e.g. FMLA in the US).",
    )
    statutory_type_code: str | None = Field(
        default=None, description="Statutory rule type (e.g. 'FMLA') when statutory_filing_indicator is True.",
    )
    leave_duration: float | None = Field(default=None, description="Expected leave duration (numeric quantity).")
    comment: str | None = Field(default=None, description="Free-text comment attached to the leave.")
    work_assignment_id: str | None = Field(
        default=None, description="Optional workAssignmentID when the worker has multiple assignments.",
    )
    reason_code: str | None = Field(default=None, description="ADP event reason code. Optional.")


class ChangeLeaveInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID of the employee.")
    leave_id: str = Field(description="Item ID of the existing leave to change (from list_worker_leaves).")
    effective_date: str = Field(description="Event effective date (YYYY-MM-DD).")
    start_date: str | None = Field(default=None, description="Updated leave start date. Omit to keep unchanged.")
    expected_end_date: str | None = Field(
        default=None, description="Updated expected end date. Omit to keep unchanged.",
    )
    leave_type_code: str | None = Field(default=None, description="Updated leave type code.")
    leave_sub_type_code: str | None = Field(default=None, description="Updated leave sub-type code.")
    payment_status_code: str | None = Field(default=None, description="Updated payment status.")
    return_date: str | None = Field(
        default=None,
        description="Updated return date — sets transform.workerLeave.leaveReturn.returnDateTime.",
    )
    return_to_work_indicator: bool | None = Field(
        default=None, description="Updated returnToWorkIndicator (paired with return_date when amending a return).",
    )
    comment: str | None = Field(default=None, description="Free-text comment attached to the change.")
    work_assignment_id: str | None = Field(default=None, description="Optional workAssignmentID.")
    reason_code: str | None = Field(default=None, description="ADP event reason code. Optional.")


class CancelLeaveInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID of the employee.")
    leave_id: str = Field(description="Item ID of the leave to cancel.")
    effective_date: str = Field(description="Event effective date (YYYY-MM-DD).")
    work_assignment_id: str | None = Field(default=None, description="Optional workAssignmentID.")
    reason_code: str | None = Field(default=None, description="ADP event reason code. Optional.")


class RequestLeaveReturnInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID of the employee.")
    leave_id: str = Field(description="Item ID of the leave the employee is returning from.")
    return_date: str = Field(description="Return-to-work date (YYYY-MM-DD).")
    return_to_work_indicator: bool = Field(
        default=True,
        description="True when the employee is returning to work. Set False if the return is being denied.",
    )
    notification_received_date: str | None = Field(
        default=None, description="Date the return notification was received by the employer.",
    )
    comment: str | None = Field(default=None, description="Free-text comment attached to the return.")
    work_assignment_id: str | None = Field(default=None, description="Optional workAssignmentID.")
    effective_date: str | None = Field(
        default=None, description="Event effective date. Defaults to return_date.",
    )
    reason_code: str | None = Field(default=None, description="ADP event reason code. Optional.")


# ---------- HTTP helpers ----------


async def _call(
    conn: ADPConnection,
    *,
    method: str,
    path: str,
    params: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{conn.api_base_url}{path}"
    validate_adp_url(url, field_name="api_base_url")
    headers = {"Authorization": f"Bearer {conn.access_token}"}

    async with build_mtls_httpx_client(conn, timeout=30.0) as client:
        response = await client.request(
            method=method, url=url, headers=headers, params=params, json=body, timeout=30.0,
        )
        if response.status_code == HTTP_UNAUTHORIZED:
            await fetch_token(conn, force=True)
            headers["Authorization"] = f"Bearer {conn.access_token}"
            response = await client.request(
                method=method, url=url, headers=headers, params=params, json=body, timeout=30.0,
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


async def _post_event(conn: ADPConnection, *, path: str, body: dict[str, Any]) -> dict[str, Any]:
    return await _call(conn, method="POST", path=path, body=body)


def build_worker_leaves_tools(
    connection: ADPConnection,
    request_cache: RequestCache,  # accepted for registry uniformity; reads don't use shared cache  # noqa: ARG001
) -> list[Tool]:
    conn = connection

    async def _list_worker_leaves(associate_oid: str, filter: str | None = None) -> dict[str, Any]:  # noqa: A002
        path = PATH_LIST_LEAVES.format(aoid=associate_oid)
        params = {"$filter": filter} if filter else None
        result = await _call(conn, method="GET", path=path, params=params)
        if "error" in result:
            return result
        return extract_worker_leaves(result.get("workerLeaves") or [])

    async def _get_worker_leave_event_meta(
        operation: str, filter: str | None = None,  # noqa: A002
    ) -> dict[str, Any]:
        path = _META_OPERATIONS[operation]
        params = {"$filter": filter} if filter else None
        return await _call(conn, method="GET", path=path, params=params)

    async def _request_worker_leave_absence(**kw: Any) -> dict[str, Any]:
        body = build_request_leave_absence_event(**kw)
        return await _post_event(conn, path=PATH_ABSENCE_REQUEST, body=body)

    async def _change_worker_leave(**kw: Any) -> dict[str, Any]:
        body = build_change_leave_event(**kw)
        return await _post_event(conn, path=PATH_LEAVE_CHANGE, body=body)

    async def _cancel_worker_leave(**kw: Any) -> dict[str, Any]:
        body = build_cancel_leave_event(**kw)
        return await _post_event(conn, path=PATH_LEAVE_CANCEL, body=body)

    async def _request_worker_leave_return(**kw: Any) -> dict[str, Any]:
        body = build_request_leave_return_event(**kw)
        return await _post_event(conn, path=PATH_LEAVE_RETURN_REQUEST, body=body)

    return [
        StructuredTool.from_function(
            name="list_worker_leaves",
            description=(
                "List an employee's leaves (absence + return entries) by ADP associate OID. "
                "Each row includes itemID (pass to change/cancel/return as `leave_id`), leave "
                "type/sub-type, start/expected-end dates, statutory flags, payment status, and "
                "return details when present. Supports an optional $filter."
            ),
            coroutine=_list_worker_leaves,
            args_schema=ListWorkerLeavesInput,
        ),
        StructuredTool.from_function(
            name="get_worker_leave_event_meta",
            description=(
                "Fetch the meta/discovery schema for a leave event (absence_request, cancel, "
                "change, or return_request). Rarely agent-facing — use when you need the set "
                "of valid codes/fields for a given event."
            ),
            coroutine=_get_worker_leave_event_meta,
            args_schema=GetLeaveEventMetaInput,
        ),
        StructuredTool.from_function(
            name="request_worker_leave_absence",
            description=(
                "Request a new leave of absence for an employee. Provide the associate OID, "
                "start_date, and leave_type_code; optional fields cover expected end date, "
                "statutory flags (e.g. FMLA), payment status, and sub-type."
            ),
            coroutine=_request_worker_leave_absence,
            args_schema=RequestLeaveAbsenceInput,
        ),
        StructuredTool.from_function(
            name="change_worker_leave",
            description=(
                "Change an existing leave. Requires the leave's itemID (from list_worker_leaves) "
                "and an effective_date. Any combination of absence fields (start/end/type) and "
                "return fields (return_date, return_to_work_indicator) may be supplied — only "
                "the supplied ones are patched."
            ),
            coroutine=_change_worker_leave,
            args_schema=ChangeLeaveInput,
        ),
        StructuredTool.from_function(
            name="cancel_worker_leave",
            description=(
                "Cancel an existing leave. Requires the leave's itemID (from list_worker_leaves) "
                "and an effective_date."
            ),
            coroutine=_cancel_worker_leave,
            args_schema=CancelLeaveInput,
        ),
        StructuredTool.from_function(
            name="request_worker_leave_return",
            description=(
                "Request an employee's return from leave. Requires the leave's itemID, a "
                "return_date, and return_to_work_indicator (default True). Set the indicator "
                "False to record a denied return."
            ),
            coroutine=_request_worker_leave_return,
            args_schema=RequestLeaveReturnInput,
        ),
    ]

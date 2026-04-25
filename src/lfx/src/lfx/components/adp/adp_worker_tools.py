"""Worker-data agent tools backed by GET /hr/v2/workers/{associateOID}."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from lfx.components.adp._shared import (
    HTTP_UNAUTHORIZED,
    ADPConnection,
    RequestCache,
    build_mtls_httpx_client,
    cached_get_json,
    fetch_token,
    validate_adp_url,
)
from lfx.field_typing import Tool


def extract_name(worker: dict[str, Any]) -> dict[str, Any]:
    person = worker.get("person", {})
    legal = person.get("legalName")
    preferred = person.get("preferredName")
    return {
        "legalName": {
            "firstName": legal.get("givenName") if legal else None,
            "middleName": legal.get("middleName") if legal else None,
            "lastName": legal.get("familyName1") if legal else None,
        }
        if legal
        else None,
        "preferredName": {
            "firstName": preferred.get("givenName") if preferred else None,
            "lastName": preferred.get("familyName1") if preferred else None,
        }
        if preferred
        else None,
    }


def extract_addresses(worker: dict[str, Any]) -> dict[str, Any]:
    person = worker.get("person", {})
    addr = person.get("legalAddress")
    if not addr:
        return {"legalAddress": None}
    subdivision = addr.get("countrySubdivisionLevel1")
    return {
        "legalAddress": {
            "lineOne": addr.get("lineOne"),
            "lineTwo": addr.get("lineTwo"),
            "cityName": addr.get("cityName"),
            "countrySubdivisionLevel1": subdivision.get("codeValue") if isinstance(subdivision, dict) else subdivision,
            "postalCode": addr.get("postalCode"),
            "countryCode": addr.get("countryCode"),
        },
    }


def extract_contact_information(worker: dict[str, Any]) -> dict[str, Any]:
    person = worker.get("person", {})
    comm = person.get("communication", {})
    return {
        "emails": comm.get("emails", []),
        "landlines": comm.get("landlines", []),
        "mobiles": comm.get("mobiles", []),
    }


def extract_job(worker: dict[str, Any]) -> dict[str, Any]:
    assignments = worker.get("workAssignments", [])
    status_obj = worker.get("workerStatus", {})
    worker_status = status_obj.get("statusCode", {}).get("codeValue") if status_obj else None

    if not assignments:
        return {
            "jobTitle": None,
            "departmentName": None,
            "locationName": None,
            "workerStatus": worker_status,
            "managementPosition": None,
            "reportsTo": None,
        }

    assignment = assignments[0]

    dept_name = None
    for unit in assignment.get("homeOrganizationalUnits", []):
        if unit.get("typeCode", {}).get("codeValue") == "Department":
            dept_name = unit.get("nameCode", {}).get("codeValue")
            break

    location = assignment.get("homeWorkLocation", {})
    location_name = location.get("nameCode", {}).get("codeValue") if location else None

    mgmt = assignment.get("managementPosition", {})
    mgmt_indicator = mgmt.get("indicatorCode", {}).get("codeValue") if mgmt else None
    mgmt_bool = mgmt_indicator.lower() == "true" if mgmt_indicator else None

    reports_list = assignment.get("reportsTo", [])
    reports_to = None
    if reports_list:
        r = reports_list[0]
        reports_to = {
            "associateOID": r.get("associateOID"),
            "workerName": r.get("reportsToWorkerName", {}).get("formattedName"),
        }

    return {
        "jobTitle": assignment.get("jobTitle"),
        "departmentName": dept_name,
        "locationName": location_name,
        "workerStatus": worker_status,
        "managementPosition": mgmt_bool,
        "reportsTo": reports_to,
    }


def _id_value(id_obj: dict[str, Any] | None) -> dict[str, Any] | None:
    if not id_obj:
        return None
    scheme = id_obj.get("schemeCode") or {}
    return {
        "idValue": id_obj.get("idValue"),
        "schemeCode": scheme.get("codeValue") if isinstance(scheme, dict) else scheme,
    }


def extract_ids(worker: dict[str, Any]) -> dict[str, Any]:
    return {
        "associateOID": worker.get("associateOID"),
        "workerID": _id_value(worker.get("workerID")),
        "alternateIDs": [_id_value(a) for a in worker.get("alternateIDs", []) if a],
    }


_WORKER_DATE_FIELDS = (
    "firstHireDate",
    "originalHireDate",
    "rehireDate",
    "adjustedServiceDate",
    "creditedServiceDate",
    "acquisitionDate",
    "earlyRetirementDate",
    "retirementDate",
    "terminationDate",
    "expectedTerminationDate",
    "leaveOfAbsenceReturnDate",
)


def extract_dates(worker: dict[str, Any]) -> dict[str, Any]:
    dates = worker.get("workerDates") or {}
    return {field: dates.get(field) for field in _WORKER_DATE_FIELDS}


def extract_status(worker: dict[str, Any]) -> dict[str, Any]:
    status = worker.get("workerStatus") or {}
    status_code = status.get("statusCode") or {}
    reason_code = status.get("reasonCode") or {}
    return {
        "statusCode": status_code.get("codeValue") if isinstance(status_code, dict) else None,
        "reasonCode": reason_code.get("codeValue") if isinstance(reason_code, dict) else None,
        "effectiveDate": status.get("effectiveDate"),
    }


def extract_business_communication(worker: dict[str, Any]) -> dict[str, Any]:
    comm = worker.get("businessCommunication") or {}
    return {
        "emails": comm.get("emails", []),
        "landlines": comm.get("landlines", []),
        "mobiles": comm.get("mobiles", []),
    }


def extract_compensation(worker: dict[str, Any]) -> dict[str, Any]:
    assignments = worker.get("workAssignments", [])
    if not assignments:
        return {"baseRemuneration": None, "additionalRemunerations": []}

    assignment = assignments[0]
    base = assignment.get("baseRemuneration")

    base_result = None
    if base:
        pay_period = base.get("payPeriodRateAmount", {})
        annual = base.get("annualRateAmount", {})
        base_result = {
            "payPeriodAmount": pay_period.get("amountValue"),
            "annualAmount": annual.get("amountValue"),
            "currencyCode": annual.get("currencyCode") or pay_period.get("currencyCode"),
            "effectiveDate": base.get("effectiveDate"),
        }

    additional = []
    for rem in assignment.get("additionalRemunerations", []):
        rate = rem.get("rate", {}).get("rateAmount", {})
        additional.append({
            "nameCode": rem.get("nameCode", {}).get("codeValue"),
            "amount": rate.get("amountValue"),
            "currencyCode": rate.get("currencyCode"),
        })

    return {
        "baseRemuneration": base_result,
        "additionalRemunerations": additional,
    }


class WorkerToolInput(BaseModel):
    associate_oid: str = Field(description="The ADP associate OID (unique employee identifier)")


async def _fetch_worker(
    conn: ADPConnection,
    associate_oid: str,
    *,
    request_cache: RequestCache,
) -> dict[str, Any]:
    url = f"{conn.api_base_url}/hr/v2/workers/{associate_oid}"
    validate_adp_url(url, field_name="api_base_url")

    async with build_mtls_httpx_client(conn, timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {conn.access_token}"}
        result = await cached_get_json(client=client, cache=request_cache, url=url, headers=headers)
        if result.get("status_code") == HTTP_UNAUTHORIZED:
            await fetch_token(conn, force=True)
            headers["Authorization"] = f"Bearer {conn.access_token}"
            result = await cached_get_json(client=client, cache=request_cache, url=url, headers=headers)

    if "error" in result:
        return result
    workers = result.get("workers", [])
    if not workers:
        return {"error": "No worker found", "status_code": 404}
    return workers[0]


def build_worker_tools(connection: ADPConnection, request_cache: RequestCache) -> list[Tool]:
    async def _get_employee_name(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_name(worker)

    async def _get_employee_addresses(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_addresses(worker)

    async def _get_employee_contact_information(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_contact_information(worker)

    async def _get_employee_job(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_job(worker)

    async def _get_employee_compensation(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_compensation(worker)

    async def _get_employee_ids(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_ids(worker)

    async def _get_employee_dates(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_dates(worker)

    async def _get_employee_status(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_status(worker)

    async def _get_employee_business_communication(associate_oid: str) -> dict[str, Any]:
        worker = await _fetch_worker(connection, associate_oid, request_cache=request_cache)
        return worker if "error" in worker else extract_business_communication(worker)

    return [
        StructuredTool.from_function(
            name="get_employee_name",
            description="Get an employee's legal and preferred name by their ADP associate OID.",
            coroutine=_get_employee_name,
            args_schema=WorkerToolInput,
        ),
        StructuredTool.from_function(
            name="get_employee_addresses",
            description="Get an employee's legal address by their ADP associate OID.",
            coroutine=_get_employee_addresses,
            args_schema=WorkerToolInput,
        ),
        StructuredTool.from_function(
            name="get_employee_contact_information",
            description="Get an employee's contact information (emails, phone numbers) by their ADP associate OID.",
            coroutine=_get_employee_contact_information,
            args_schema=WorkerToolInput,
        ),
        StructuredTool.from_function(
            name="get_employee_job",
            description="Get an employee's job details (title, department, location, manager) by their ADP associate OID.",
            coroutine=_get_employee_job,
            args_schema=WorkerToolInput,
        ),
        StructuredTool.from_function(
            name="get_employee_compensation",
            description="Get an employee's compensation details (base pay, additional remunerations) by their ADP associate OID.",
            coroutine=_get_employee_compensation,
            args_schema=WorkerToolInput,
        ),
        StructuredTool.from_function(
            name="get_employee_ids",
            description="Get an employee's identifiers (associateOID, workerID, alternateIDs) by their ADP associate OID.",
            coroutine=_get_employee_ids,
            args_schema=WorkerToolInput,
        ),
        StructuredTool.from_function(
            name="get_employee_dates",
            description=(
                "Get an employee's lifecycle dates (first hire, original hire, rehire, "
                "termination, retirement, leave-return, etc.) by their ADP associate OID."
            ),
            coroutine=_get_employee_dates,
            args_schema=WorkerToolInput,
        ),
        StructuredTool.from_function(
            name="get_employee_status",
            description=(
                "Get an employee's current worker status (active/terminated/leave), "
                "status reason, and effective date by their ADP associate OID."
            ),
            coroutine=_get_employee_status,
            args_schema=WorkerToolInput,
        ),
        StructuredTool.from_function(
            name="get_employee_business_communication",
            description=(
                "Get an employee's business communication channels (work email, work phone, "
                "work mobile) by their ADP associate OID. Distinct from personal contact info."
            ),
            coroutine=_get_employee_business_communication,
            args_schema=WorkerToolInput,
        ),
    ]

"""ADP job-applicant screening/assessment mutation tools — module-level builder.

Backs the ADP WFN `staffing/job-applicants v2` tile. The tile is all-mutations,
covering four ADP → third-party-screening-vendor integration endpoints:

- `external-assessment.status.change` — update assessment result status for applicants
- `external-screening.initiate` — initiate a background screening for applicants
- `external-screening.status.change` — update background-screening status for applicants
- `external-screening.packages.modify` — publish or modify screening/assessment packages

The three per-applicant endpoints share a `jobApplications[]` transform shape
and are consolidated into `manage_applicant_screening`. The package-modify
endpoint has its own shape and is exposed as `publish_screening_packages`.
Both tools gated behind `enable_mutations`.
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

PATH_ASSESSMENT_STATUS = "/events/staffing/v1/job-applicant.external-assessment.status.change"
PATH_SCREENING_INITIATE = "/events/staffing/v1/job-applicant.external-screening.initiate"
PATH_SCREENING_STATUS = "/events/staffing/v1/job-applicant.external-screening.status.change"
PATH_PACKAGES_MODIFY = "/events/staffing/v1/job-applicant.external-screening.packages.modify"

_APPLICANT_ACTION_PATHS: dict[str, str] = {
    "update_assessment_status": PATH_ASSESSMENT_STATUS,
    "initiate_screening": PATH_SCREENING_INITIATE,
    "update_screening_status": PATH_SCREENING_STATUS,
}


def _build_link(link: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if link.get("href") is not None:
        out["href"] = link["href"]
    if link.get("link_expiration_date"):
        out["linkExpirationDate"] = link["link_expiration_date"]
    return out


def _build_application(
    item: dict[str, Any],
    *,
    action: str,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if item.get("application_id"):
        out["applicationID"] = item["application_id"]

    inner: dict[str, Any] = {}
    if action == "update_assessment_status":
        if item.get("status_code"):
            inner["assessmentStatusCode"] = {"codeValue": item["status_code"]}
        if item.get("package_id"):
            inner["assessmentPackageID"] = item["package_id"]
        if item.get("links"):
            inner["links"] = [_build_link(link) for link in item["links"]]
        if inner:
            out["externalAssessment"] = inner
    elif action == "initiate_screening":
        if item.get("package_id"):
            inner["screeningPackageID"] = item["package_id"]
        if item.get("links"):
            inner["links"] = [_build_link(link) for link in item["links"]]
        if inner:
            out["externalBackgroundScreening"] = inner
    elif action == "update_screening_status":
        if item.get("status_code"):
            inner["screeningStatusCode"] = {"codeValue": item["status_code"]}
        if item.get("links"):
            inner["links"] = [_build_link(link) for link in item["links"]]
        if inner:
            out["externalBackgroundScreening"] = inner
    return out


def build_applicant_screening_event(
    *,
    action: Literal["update_assessment_status", "initiate_screening", "update_screening_status"],
    agency_code: str,
    applications: list[dict[str, Any]],
    screening_type_code: str | None = None,
    additional_transform_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_context: dict[str, Any] = {"agencyCode": {"codeValue": agency_code}}
    if screening_type_code:
        event_context["screeningTypeCode"] = {"codeValue": screening_type_code}

    transform: dict[str, Any] = {
        "jobApplications": [_build_application(app, action=action) for app in applications],
    }
    if additional_transform_fields:
        transform.update(additional_transform_fields)

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


def _build_package(item: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if item.get("screening_package_id"):
        out["screeningPackageID"] = item["screening_package_id"]
    if item.get("package_name"):
        out["packageName"] = item["package_name"]
    if item.get("package_description"):
        out["packageDescription"] = item["package_description"]
    if item.get("package_status_code"):
        out["packageStatusCode"] = {"codeValue": item["package_status_code"]}
    if item.get("package_amount") is not None:
        amount: dict[str, Any] = {"amountValue": item["package_amount"]}
        # Match HAR samples: empty-string currency is allowed; if omitted, default to "USD".
        currency_code = item.get("currency_code")
        if currency_code is None:
            currency_code = "USD"
        amount["currencyCode"] = currency_code
        out["packageAmount"] = amount
    if item.get("effective_date"):
        out["screeningLinkEffectiveDate"] = item["effective_date"]
    if item.get("expiration_date"):
        out["screeningLinkExpirationDate"] = item["expiration_date"]
    return out


def build_packages_modify_event(
    *,
    agency_code: str,
    screening_type_code: str,
    packages: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "events": [
            {
                "data": {
                    "eventContext": {
                        "screeningTypeCode": {"codeValue": screening_type_code},
                        "agencyCode": {"codeValue": agency_code},
                    },
                    "transform": {
                        "externalScreeningPackages": [_build_package(p) for p in packages],
                    },
                },
            },
        ],
    }


class ScreeningLink(BaseModel):
    href: str = Field(description="URL to the screening/assessment results or launch page.")
    link_expiration_date: str | None = Field(
        default=None, description="ISO-8601 date when the link expires (optional).",
    )


class ApplicantScreeningEntry(BaseModel):
    application_id: str = Field(description="ADP job-application ID (itemID of the application).")
    package_id: str | None = Field(
        default=None,
        description="Screening or assessment package ID. Used for initiate_screening and update_assessment_status.",
    )
    status_code: str | None = Field(
        default=None,
        description="Status code (e.g. 'Complete', 'In Progress', 'NEW'). Used for update_*_status actions.",
    )
    links: list[ScreeningLink] = Field(
        default_factory=list, description="Result/launch links for this applicant.",
    )


class ManageApplicantScreeningInput(BaseModel):
    action: Literal["update_assessment_status", "initiate_screening", "update_screening_status"] = Field(
        description=(
            "Which event to fire: 'update_assessment_status' updates assessment results, "
            "'initiate_screening' kicks off a new background screening, "
            "'update_screening_status' updates background-screening status."
        ),
    )
    agency_code: str = Field(description="Screening-agency vendor code (e.g. 'Agency1', 'PartnerName').")
    screening_type_code: str | None = Field(
        default=None,
        description="Screening type code (e.g. 'ASSESSMENT'). Required for initiate_screening.",
    )
    applications: list[ApplicantScreeningEntry] = Field(
        description="One or more applicants to act on.",
    )
    additional_transform_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Escape hatch: extra fields merged into the transform object.",
    )


class ScreeningPackage(BaseModel):
    screening_package_id: str = Field(description="Package identifier.")
    package_name: str | None = Field(default=None, description="Human-readable package name.")
    package_description: str | None = Field(default=None, description="Package description.")
    package_status_code: str | None = Field(
        default=None, description="Status code (e.g. 'Assessment', 'TEST').",
    )
    package_amount: float | None = Field(default=None, description="Price of the package.")
    currency_code: str | None = Field(
        default=None,
        description=(
            "ISO-4217 currency for package_amount. Defaults to 'USD'. Pass empty string "
            "to match HAR samples that elide currency."
        ),
    )
    effective_date: str | None = Field(
        default=None,
        description="ISO-8601 date when the screening link/package becomes effective.",
    )
    expiration_date: str | None = Field(
        default=None, description="ISO-8601 date when the screening link/package expires.",
    )


class PublishScreeningPackagesInput(BaseModel):
    agency_code: str = Field(description="Screening-agency vendor code.")
    screening_type_code: str = Field(
        description="Screening type code (e.g. 'ASSESSMENT', 'BACKGROUND_CHECK').",
    )
    packages: list[ScreeningPackage] = Field(description="One or more packages to publish/modify.")


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


def build_job_applicants_tools(
    connection: ADPConnection,
    request_cache: RequestCache,  # noqa: ARG001 — accepted for registry uniformity; unused for writes
    *,
    enable_mutations: bool = False,
) -> list[Tool]:
    """Build ADP job-applicant screening mutation tools.

    Returns up to 2 StructuredTools for applicant screening management and
    package publishing. Both gated behind enable_mutations. Writes never
    consult the request_cache.
    """
    if not enable_mutations:
        return []

    conn = connection

    async def _manage_applicant_screening(**kwargs: Any) -> dict[str, Any]:
        normalized = dict(kwargs)
        apps = normalized.get("applications") or []
        normalized_apps: list[dict[str, Any]] = []
        for app in apps:
            app_dict = app.model_dump() if hasattr(app, "model_dump") else dict(app)
            links = app_dict.get("links") or []
            app_dict["links"] = [
                link.model_dump() if hasattr(link, "model_dump") else link for link in links
            ]
            normalized_apps.append(app_dict)
        normalized["applications"] = normalized_apps

        action = normalized["action"]
        body = build_applicant_screening_event(**normalized)
        path = _APPLICANT_ACTION_PATHS[action]
        return await _post_event(conn, path=path, body=body)

    async def _publish_screening_packages(**kwargs: Any) -> dict[str, Any]:
        normalized = dict(kwargs)
        packages = normalized.get("packages") or []
        normalized["packages"] = [
            pkg.model_dump() if hasattr(pkg, "model_dump") else pkg for pkg in packages
        ]
        body = build_packages_modify_event(**normalized)
        return await _post_event(conn, path=PATH_PACKAGES_MODIFY, body=body)

    return [
        StructuredTool.from_function(
            name="manage_applicant_screening",
            description=(
                "Manage screening/assessment events for one or more job applicants. Set "
                "`action='initiate_screening'` to start a background screening, "
                "`'update_screening_status'` to update screening status, or "
                "`'update_assessment_status'` to update assessment results. Requires "
                "`agency_code` and a list of `applications` (each with application_id, "
                "optionally package_id, status_code, and result links)."
            ),
            coroutine=_manage_applicant_screening,
            args_schema=ManageApplicantScreeningInput,
        ),
        StructuredTool.from_function(
            name="publish_screening_packages",
            description=(
                "Publish or modify one or more screening/assessment packages offered by a "
                "screening agency. Each package has a name, description, status, price, "
                "and effective/expiration dates."
            ),
            coroutine=_publish_screening_packages,
            args_schema=PublishScreeningPackagesInput,
        ),
    ]


# ---------------------------------------------------------------------------
# Back-compat stub — preserved for __init__.py / test_bundle_init.py imports.
# ---------------------------------------------------------------------------
class ADPJobApplicantsToolsComponent:
    name = "ADPJobApplicantsTools"

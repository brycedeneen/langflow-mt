"""ADP applicant onboarding tools — module-level builder.

Backs the ADP WFN `applicant-onboarding v2` tile. Wraps POST
`/hcm/v2/applicant.onboard` (both `inprogress` and `complete` statuses) as a
single tool with narrow structured args for the most-used fields across US,
CA, and International templates, plus `additional_fields` for tax profile,
WC coverage, custom fields, and anything else the narrow args don't cover.
Gated behind `enable_mutations` — this creates a real applicant record.
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

PATH_APPLICANT_ONBOARD = "/hcm/v2/applicant.onboard"


def _code(value: str | None) -> dict[str, Any] | None:
    return {"code": value} if value else None


def _deep_merge(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst


def _birth_name(first_name: str, last_name: str, middle_name: str | None) -> dict[str, Any]:
    name: dict[str, Any] = {"givenName": first_name, "familyName": last_name}
    if middle_name:
        name["middleName"] = middle_name
    return name


def _legal_address(
    *,
    line1: str | None,
    city: str | None,
    state: str | None,
    postal: str | None,
    country: str | None,
) -> dict[str, Any] | None:
    if not any((line1, city, state, postal, country)):
        return None
    addr: dict[str, Any] = {}
    if line1:
        addr["lineOne"] = line1
    if city:
        addr["cityName"] = city
    if state:
        addr["subdivisionCode"] = {"code": state}
    if postal:
        addr["postalCode"] = postal
    if country:
        addr["countryCode"] = country
    return addr


def _communication(email: str | None, phone_mobile: str | None) -> dict[str, Any] | None:
    comm: dict[str, Any] = {}
    if email:
        comm["emails"] = [{"emailUri": email}]
    if phone_mobile:
        comm["mobiles"] = [{"dialNumber": phone_mobile}]
    return comm or None


def _personal_profile(
    *,
    first_name: str,
    last_name: str,
    middle_name: str | None,
    preferred_first_name: str | None,
    birth_date: str | None,
    gender_code: str | None,
    ssn: str | None,
    email: str | None,
    phone_mobile: str | None,
    legal_address_line1: str | None,
    legal_address_city: str | None,
    legal_address_state: str | None,
    legal_address_postal: str | None,
    legal_address_country: str | None,
) -> dict[str, Any]:
    profile: dict[str, Any] = {"birthName": _birth_name(first_name, last_name, middle_name)}
    if preferred_first_name:
        profile["preferredName"] = {"nickName": preferred_first_name}
    if birth_date:
        profile["birthDate"] = birth_date
    if gender_code:
        profile["genderCode"] = {"code": gender_code}
    if ssn:
        profile["governmentIDs"] = [{"id": ssn, "nameCode": {"code": "SSN"}}]
    addr = _legal_address(
        line1=legal_address_line1, city=legal_address_city,
        state=legal_address_state, postal=legal_address_postal,
        country=legal_address_country,
    )
    if addr:
        profile["legalAddress"] = addr
    comm = _communication(email, phone_mobile)
    if comm:
        profile["communication"] = comm
    return profile


def _worker_profile(
    *,
    hire_date: str,
    job_code: str | None,
    home_work_location_code: str | None,
    home_department_code: str | None,
    worker_type_code: str | None,
    reports_to_position_id: str | None,
) -> dict[str, Any]:
    profile: dict[str, Any] = {"hireDate": hire_date}
    if home_work_location_code:
        profile["homeWorkLocation"] = {"nameCode": {"code": home_work_location_code}}
    if job_code:
        profile["job"] = {"jobCode": {"code": job_code}}
    if home_department_code:
        profile["homeOrganizationalUnits"] = [
            {
                "unitTypeCode": {"code": "HomeDepartment"},
                "nameCode": {"code": home_department_code},
            },
        ]
    if worker_type_code:
        profile["workerTypeCode"] = {"code": worker_type_code}
    if reports_to_position_id:
        profile["reportsTo"] = {"positionID": reports_to_position_id}
    return profile


def _payroll_profile(
    *,
    payroll_group_code: str | None,
    pay_period_amount: float | None,
    pay_period_currency: str,
    pay_cycle_code: str | None,
    standard_hours: float | None,
) -> dict[str, Any] | None:
    profile: dict[str, Any] = {}
    if payroll_group_code:
        profile["payrollGroupCode"] = payroll_group_code
    if pay_period_amount is not None:
        profile["baseRemuneration"] = {
            "payPeriodRateAmount": {
                "amount": str(pay_period_amount),
                "currencyCode": pay_period_currency,
            },
        }
    if standard_hours is not None:
        profile["standardHours"] = {"hoursQuantity": str(standard_hours)}
    if pay_cycle_code:
        profile["payCycleCode"] = {"code": pay_cycle_code}
    return profile or None


def build_applicant_onboarding_body(
    *,
    # Required
    onboarding_template_code: str,
    status: str,
    first_name: str,
    last_name: str,
    hire_date: str,
    # Country / template hints
    country_code: str | None = None,
    pre_hire: bool | None = None,
    onboarding_experience_code: str | None = None,
    # Name extras
    middle_name: str | None = None,
    preferred_first_name: str | None = None,
    # Personal
    birth_date: str | None = None,
    gender_code: str | None = None,
    ssn: str | None = None,
    email: str | None = None,
    phone_mobile: str | None = None,
    # Address
    legal_address_line1: str | None = None,
    legal_address_city: str | None = None,
    legal_address_state: str | None = None,
    legal_address_postal: str | None = None,
    legal_address_country: str | None = None,
    # Work
    job_code: str | None = None,
    home_work_location_code: str | None = None,
    home_department_code: str | None = None,
    worker_type_code: str | None = None,
    reports_to_position_id: str | None = None,
    # Payroll
    payroll_group_code: str | None = None,
    pay_period_amount: float | None = None,
    pay_period_currency: str = "USD",
    pay_cycle_code: str | None = None,
    standard_hours: float | None = None,
    # US I-9
    employment_eligibility_option_code: str | None = None,
    employment_eligibility_location_code: str | None = None,
    # Escape hatch
    additional_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    onboarding: dict[str, Any] = {
        "onboardingTemplateCode": {"code": onboarding_template_code},
        "onboardingStatus": {"statusCode": {"code": status}},
    }
    if country_code:
        onboarding["countryCode"] = country_code
    if onboarding_experience_code:
        onboarding["onboardingExperienceCode"] = {"code": onboarding_experience_code}
    if employment_eligibility_option_code:
        onboarding["employmentEligibilityOptionCode"] = {"code": employment_eligibility_option_code}
    if pre_hire is not None:
        onboarding["preHireIndicator"] = pre_hire
    if employment_eligibility_location_code:
        onboarding["employmentEligibilityProfile"] = {
            "employerOrganization": {
                "locationNameCode": {"code": employment_eligibility_location_code},
            },
        }
    onboarding["applicantPersonalProfile"] = _personal_profile(
        first_name=first_name,
        last_name=last_name,
        middle_name=middle_name,
        preferred_first_name=preferred_first_name,
        birth_date=birth_date,
        gender_code=gender_code,
        ssn=ssn,
        email=email,
        phone_mobile=phone_mobile,
        legal_address_line1=legal_address_line1,
        legal_address_city=legal_address_city,
        legal_address_state=legal_address_state,
        legal_address_postal=legal_address_postal,
        legal_address_country=legal_address_country,
    )
    onboarding["applicantWorkerProfile"] = _worker_profile(
        hire_date=hire_date,
        job_code=job_code,
        home_work_location_code=home_work_location_code,
        home_department_code=home_department_code,
        worker_type_code=worker_type_code,
        reports_to_position_id=reports_to_position_id,
    )
    payroll = _payroll_profile(
        payroll_group_code=payroll_group_code,
        pay_period_amount=pay_period_amount,
        pay_period_currency=pay_period_currency,
        pay_cycle_code=pay_cycle_code,
        standard_hours=standard_hours,
    )
    if payroll:
        onboarding["applicantPayrollProfile"] = payroll
    if additional_fields:
        _deep_merge(onboarding, additional_fields)
    return {"applicantOnboarding": onboarding}


class InitiateApplicantOnboardingInput(BaseModel):
    onboarding_template_code: str = Field(
        description=(
            "ADP onboarding template code (e.g. '9200525655723_1'). "
            "Template implies US/CA unless country_code is set."
        ),
    )
    status: Literal["inprogress", "complete"] = Field(
        description="'inprogress' to start an onboarding that will be finished later; 'complete' for a full hire.",
    )
    first_name: str = Field(description="Applicant's legal given name.")
    last_name: str = Field(description="Applicant's legal family name.")
    hire_date: str = Field(description="Hire date (YYYY-MM-DD).")
    country_code: str | None = Field(
        default=None,
        description=(
            "ISO country code (e.g. 'FR', 'DE'). Required for International templates; "
            "omit for US/CA (template implies it)."
        ),
    )
    pre_hire: bool | None = Field(
        default=None,
        description="True if this is a pre-hire record (applicant offered but not yet onboarded).",
    )
    onboarding_experience_code: str | None = Field(
        default=None,
        description="Onboarding experience variant, e.g. 'default'. Typically set for full hires.",
    )
    middle_name: str | None = Field(default=None, description="Middle name (legal).")
    preferred_first_name: str | None = Field(default=None, description="Preferred/nickname first name.")
    birth_date: str | None = Field(default=None, description="Birth date (YYYY-MM-DD).")
    gender_code: str | None = Field(default=None, description="Gender code (e.g. 'M', 'F').")
    ssn: str | None = Field(default=None, description="US SSN. Stored as governmentID with nameCode=SSN.")
    email: str | None = Field(default=None, description="Personal email.")
    phone_mobile: str | None = Field(default=None, description="Mobile dial number (digits only).")
    legal_address_line1: str | None = Field(default=None, description="Legal address line 1.")
    legal_address_city: str | None = Field(default=None, description="Legal address city.")
    legal_address_state: str | None = Field(
        default=None, description="State/province subdivision code (e.g. 'GA', 'ON').",
    )
    legal_address_postal: str | None = Field(default=None, description="Postal/zip code.")
    legal_address_country: str | None = Field(
        default=None, description="ISO country code for the address (e.g. 'US').",
    )
    job_code: str | None = Field(default=None, description="ADP job code.")
    home_work_location_code: str | None = Field(
        default=None, description="Home work-location code (ADP locationNameCode).",
    )
    home_department_code: str | None = Field(
        default=None, description="Home department code (HomeDepartment organizational unit).",
    )
    worker_type_code: str | None = Field(
        default=None, description="Worker type (e.g. 'F' for full-time, 'P' part-time).",
    )
    reports_to_position_id: str | None = Field(
        default=None, description="Manager's position ID the new hire reports to.",
    )
    payroll_group_code: str | None = Field(default=None, description="Payroll group code.")
    pay_period_amount: float | None = Field(
        default=None, description="Base pay per pay period (e.g. 3000).",
    )
    pay_period_currency: str = Field(default="USD", description="ISO-4217 currency code.")
    pay_cycle_code: str | None = Field(
        default=None, description="Pay cycle code (e.g. 'B' biweekly, 'W' weekly, 'M' monthly).",
    )
    standard_hours: float | None = Field(
        default=None, description="Standard hours per pay period (e.g. 80 for biweekly full-time).",
    )
    employment_eligibility_option_code: str | None = Field(
        default=None, description="US I-9 option code (ADP-specific, e.g. '0').",
    )
    employment_eligibility_location_code: str | None = Field(
        default=None, description="US I-9 employer-organization location code.",
    )
    additional_fields: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Escape hatch: ADP-shaped fields deep-merged into `applicantOnboarding` "
            "(e.g. applicantTaxProfile, workersCompensationCoverage, customFieldGroup, "
            "additional organizationalUnits, SOC/school-district classifications)."
        ),
    )


async def _post_onboarding(conn: ADPConnection, body: dict[str, Any]) -> dict[str, Any]:
    url = f"{conn.api_base_url}{PATH_APPLICANT_ONBOARD}"
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


def build_applicant_onboarding_tools(
    connection: ADPConnection,
    request_cache: RequestCache,  # noqa: ARG001 — accepted for registry uniformity; unused for writes
    *,
    enable_mutations: bool = False,
) -> list[Tool]:
    """Build ADP applicant onboarding tools.

    Returns up to 1 StructuredTool for initiating applicant onboarding.
    Gated behind enable_mutations. Writes never consult the request_cache.
    """
    if not enable_mutations:
        return []

    conn = connection

    async def _initiate_applicant_onboarding(**kw: Any) -> dict[str, Any]:
        body = build_applicant_onboarding_body(**kw)
        return await _post_onboarding(conn, body)

    return [
        StructuredTool.from_function(
            name="initiate_applicant_onboarding",
            description=(
                "Start applicant onboarding in ADP. Supports both `inprogress` "
                "(minimal fields — finish later in ADP UI) and `complete` (full hire). "
                "Required: onboarding_template_code, status, first_name, last_name, "
                "hire_date. Optional fields cover personal, address, work, payroll, "
                "and US I-9 data. Use `additional_fields` to pass tax profile, "
                "workers-comp, custom fields, or state-specific extensions."
            ),
            coroutine=_initiate_applicant_onboarding,
            args_schema=InitiateApplicantOnboardingInput,
        ),
    ]


# ---------------------------------------------------------------------------
# Back-compat stub — preserved for __init__.py / test_bundle_init.py imports.
# ---------------------------------------------------------------------------
class ADPApplicantOnboardingToolsComponent:
    name = "ADPApplicantOnboardingTools"

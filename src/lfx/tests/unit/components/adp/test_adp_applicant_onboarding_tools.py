"""Tests for adp_applicant_onboarding_tools — body builders and build_applicant_onboarding_tools."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_applicant_onboarding_tools import (
    PATH_APPLICANT_ONBOARD,
    build_applicant_onboarding_body,
    build_applicant_onboarding_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


# ---------- builder: minimal / inprogress flavors ----------


def test_build_body_minimal_international():
    """Mirrors HAR sample 03: Inprogress International minimal payload."""
    body = build_applicant_onboarding_body(
        onboarding_template_code="9201031817993_1",
        status="inprogress",
        first_name="Test",
        middle_name="The",
        last_name="Hire",
        hire_date="2024-09-02",
        country_code="FR",
    )
    ob = body["applicantOnboarding"]
    assert ob["onboardingTemplateCode"] == {"code": "9201031817993_1"}
    assert ob["countryCode"] == "FR"
    assert ob["onboardingStatus"] == {"statusCode": {"code": "inprogress"}}
    assert ob["applicantPersonalProfile"]["birthName"] == {
        "givenName": "Test", "middleName": "The", "familyName": "Hire",
    }
    assert ob["applicantWorkerProfile"] == {"hireDate": "2024-09-02"}
    # Minimal Int'l has no payroll profile
    assert "applicantPayrollProfile" not in ob


def test_build_body_minimal_ca_with_payroll_group_and_empty_tax_profile():
    """Mirrors HAR sample 02: CA minimal — requires payrollGroupCode + empty tax profile."""
    body = build_applicant_onboarding_body(
        onboarding_template_code="9203338607711_1",
        status="inprogress",
        first_name="Canada",
        last_name="Test",
        hire_date="2024-09-02",
        payroll_group_code="{{payrollGroupCode}}",
        additional_fields={"applicantTaxProfile": {}},
    )
    ob = body["applicantOnboarding"]
    assert ob["applicantPayrollProfile"] == {"payrollGroupCode": "{{payrollGroupCode}}"}
    # additional_fields merged the empty tax profile through
    assert ob["applicantTaxProfile"] == {}
    # CA template doesn't require countryCode
    assert "countryCode" not in ob


# ---------- builder: full hire ----------


def test_build_body_full_us_hire():
    """Covers the US complete-hire flavor: preHire + I-9 + address + job + payroll."""
    body = build_applicant_onboarding_body(
        onboarding_template_code="9200525655723_1",
        status="complete",
        first_name="Tom",
        middle_name="M",
        last_name="Taylor",
        hire_date="2024-09-02",
        pre_hire=True,
        onboarding_experience_code="default",
        employment_eligibility_option_code="0",
        employment_eligibility_location_code="2554683735_1",
        birth_date="1989-01-01",
        gender_code="M",
        email="email@test.com",
        phone_mobile="2275237",
        legal_address_line1="5800 Windward Plaza",
        legal_address_city="Alpharetta",
        legal_address_state="GA",
        legal_address_postal="30005",
        legal_address_country="US",
        job_code="AA",
        home_work_location_code="001",
        home_department_code="101000",
        worker_type_code="F",
        payroll_group_code="{{payrollGroupCode}}",
        pay_period_amount=3000,
        pay_cycle_code="B",
        standard_hours=80,
    )
    ob = body["applicantOnboarding"]
    assert ob["onboardingStatus"]["statusCode"]["code"] == "complete"
    assert ob["preHireIndicator"] is True
    assert ob["onboardingExperienceCode"] == {"code": "default"}
    assert ob["employmentEligibilityOptionCode"] == {"code": "0"}
    assert ob["employmentEligibilityProfile"] == {
        "employerOrganization": {"locationNameCode": {"code": "2554683735_1"}},
    }

    pp = ob["applicantPersonalProfile"]
    assert pp["birthName"] == {"givenName": "Tom", "middleName": "M", "familyName": "Taylor"}
    assert pp["birthDate"] == "1989-01-01"
    assert pp["genderCode"] == {"code": "M"}
    assert pp["legalAddress"] == {
        "lineOne": "5800 Windward Plaza",
        "cityName": "Alpharetta",
        "subdivisionCode": {"code": "GA"},
        "postalCode": "30005",
        "countryCode": "US",
    }
    assert pp["communication"] == {
        "emails": [{"emailUri": "email@test.com"}],
        "mobiles": [{"dialNumber": "2275237"}],
    }

    wp = ob["applicantWorkerProfile"]
    assert wp["hireDate"] == "2024-09-02"
    assert wp["homeWorkLocation"] == {"nameCode": {"code": "001"}}
    assert wp["job"] == {"jobCode": {"code": "AA"}}
    assert wp["homeOrganizationalUnits"] == [
        {"unitTypeCode": {"code": "HomeDepartment"}, "nameCode": {"code": "101000"}},
    ]
    assert wp["workerTypeCode"] == {"code": "F"}

    payroll = ob["applicantPayrollProfile"]
    assert payroll["payrollGroupCode"] == "{{payrollGroupCode}}"
    assert payroll["baseRemuneration"] == {
        "payPeriodRateAmount": {"amount": "3000", "currencyCode": "USD"},
    }
    assert payroll["standardHours"] == {"hoursQuantity": "80"}
    assert payroll["payCycleCode"] == {"code": "B"}


def test_build_body_ssn_adds_government_id():
    body = build_applicant_onboarding_body(
        onboarding_template_code="T", status="inprogress",
        first_name="A", last_name="B", hire_date="2026-01-01",
        ssn="123-45-6789",
    )
    pp = body["applicantOnboarding"]["applicantPersonalProfile"]
    assert pp["governmentIDs"] == [{"id": "123-45-6789", "nameCode": {"code": "SSN"}}]


def test_build_body_additional_fields_deep_merge():
    """additional_fields should deep-merge into applicantOnboarding, not overwrite siblings."""
    body = build_applicant_onboarding_body(
        onboarding_template_code="T", status="complete",
        first_name="A", last_name="B", hire_date="2026-01-01",
        legal_address_line1="1 Main St", legal_address_city="X", legal_address_state="GA",
        additional_fields={
            "applicantTaxProfile": {
                "usFederalTaxInstruction": {
                    "federalIncomeTaxInstruction": {"taxFilingStatusCode": {"code": "S"}},
                },
            },
            "applicantPersonalProfile": {
                # Deep-merged into the existing applicantPersonalProfile
                "raceCode": {"code": "1"},
            },
        },
    )
    ob = body["applicantOnboarding"]
    # existing-from-args still there
    assert ob["applicantPersonalProfile"]["legalAddress"]["lineOne"] == "1 Main St"
    # merged from additional_fields
    assert ob["applicantPersonalProfile"]["raceCode"] == {"code": "1"}
    assert ob["applicantTaxProfile"]["usFederalTaxInstruction"][
        "federalIncomeTaxInstruction"]["taxFilingStatusCode"] == {"code": "S"}


def test_build_body_payroll_omitted_when_no_payroll_fields():
    body = build_applicant_onboarding_body(
        onboarding_template_code="T", status="inprogress",
        first_name="A", last_name="B", hire_date="2026-01-01",
    )
    assert "applicantPayrollProfile" not in body["applicantOnboarding"]


# ---------- mutation gate / tool routing ----------


def test_build_tools_disabled_returns_empty():
    tools = build_applicant_onboarding_tools(
        _make_connection(), RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=False,
    )
    assert tools == []


def test_build_tools_enabled_returns_one_tool():
    tools = build_applicant_onboarding_tools(
        _make_connection(), RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True,
    )
    assert {t.name for t in tools} == {"initiate_applicant_onboarding"}


@pytest.mark.asyncio
async def test_tool_invocation_posts_to_correct_path_with_envelope():
    conn = _make_connection()
    mock_client = MagicMock()
    mock_client.request = AsyncMock(
        return_value=httpx.Response(200, json={"alternateIDs": [{"idValue": "12345"}]}),
    )

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30.0):  # noqa: ARG001
        yield mock_client

    with patch(
        "lfx.components.adp.adp_applicant_onboarding_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ):
        tools = build_applicant_onboarding_tools(
            conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True,
        )
        tool = tools[0]
        await tool.ainvoke({
            "onboarding_template_code": "T1",
            "status": "inprogress",
            "first_name": "A", "last_name": "B", "hire_date": "2026-01-01",
        })

    call_kwargs = mock_client.request.call_args.kwargs
    assert PATH_APPLICANT_ONBOARD in call_kwargs.get("url", "")
    body = call_kwargs.get("json", {})
    assert "applicantOnboarding" in body
    assert body["applicantOnboarding"]["onboardingTemplateCode"] == {"code": "T1"}
    assert body["applicantOnboarding"]["onboardingStatus"] == {"statusCode": {"code": "inprogress"}}


@pytest.mark.asyncio
async def test_post_onboarding_401_retries():
    """End-to-end: verify _post_onboarding performs a 401-refresh retry."""
    conn = _make_connection()
    responses = [
        httpx.Response(401, json={"error": "expired"}),
        httpx.Response(200, json={"ok": True}),
    ]
    mock_client = MagicMock()
    mock_client.request = AsyncMock(side_effect=responses)

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30.0):  # noqa: ARG001
        yield mock_client

    async def fake_force_refresh(c, *, force=False):
        assert force is True
        c.access_token = "refreshed"  # noqa: S105

    with patch(
        "lfx.components.adp.adp_applicant_onboarding_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch(
        "lfx.components.adp.adp_applicant_onboarding_tools.fetch_token",
        new=AsyncMock(side_effect=fake_force_refresh),
    ):
        tools = build_applicant_onboarding_tools(
            conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True,
        )
        await tools[0].ainvoke({
            "onboarding_template_code": "T1",
            "status": "inprogress",
            "first_name": "A", "last_name": "B", "hire_date": "2026-01-01",
        })

    assert mock_client.request.call_count == 2

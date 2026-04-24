"""Tests for ADPApplicantOnboardingToolsComponent."""

from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.adp.adp_applicant_onboarding_tools import (
    ADPApplicantOnboardingToolsComponent,
    PATH_APPLICANT_ONBOARD,
    build_applicant_onboarding_body,
)


def _make_component(connection, *, enable_mutations: bool = False):
    return ADPApplicantOnboardingToolsComponent(
        connection=connection, enable_mutations=enable_mutations,
    )


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


@pytest.mark.asyncio
async def test_build_tools_disabled_returns_empty(adp_connection):
    c = _make_component(adp_connection, enable_mutations=False)
    assert await c.build_tools() == []


@pytest.mark.asyncio
async def test_build_tools_enabled_returns_one_tool(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    tools = await c.build_tools()
    assert {t.name for t in tools} == {"initiate_applicant_onboarding"}


@pytest.mark.asyncio
async def test_tool_invocation_posts_to_correct_path_with_envelope(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"alternateIDs": [{"idValue": "12345"}]})

    with patch.object(c, "_post_onboarding", new=mock_post):
        tools = await c.build_tools()
        tool = tools[0]
        await tool.ainvoke({
            "onboarding_template_code": "T1",
            "status": "inprogress",
            "first_name": "A", "last_name": "B", "hire_date": "2026-01-01",
        })

    call = mock_post.call_args
    assert call.args[0] is adp_connection
    body = call.args[1]
    assert "applicantOnboarding" in body
    assert body["applicantOnboarding"]["onboardingTemplateCode"] == {"code": "T1"}
    assert body["applicantOnboarding"]["onboardingStatus"] == {"statusCode": {"code": "inprogress"}}


@pytest.mark.asyncio
async def test_post_onboarding_hits_correct_url(adp_connection):
    """End-to-end: verify _post_onboarding builds the correct URL from the connection."""
    from contextlib import asynccontextmanager

    import httpx
    from unittest.mock import MagicMock

    c = _make_component(adp_connection, enable_mutations=True)
    fake_response = httpx.Response(200, json={"ok": True})
    mock_client = MagicMock()
    captured: dict = {}

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30.0):
        yield mock_client

    async def fake_execute(_client, *, url, headers, json_body, timeout):  # noqa: ARG001
        captured["url"] = url
        captured["body"] = json_body
        return fake_response

    with patch(
        "lfx.components.adp.adp_applicant_onboarding_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=fake_execute):
        result = await c._post_onboarding(adp_connection, {"applicantOnboarding": {}})

    assert captured["url"].endswith(PATH_APPLICANT_ONBOARD)
    assert result == {"ok": True}

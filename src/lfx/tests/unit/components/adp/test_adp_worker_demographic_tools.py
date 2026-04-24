"""Tests for ADPWorkerDemographicToolsComponent."""

from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.adp.adp_worker_demographic_tools import (
    ADPWorkerDemographicToolsComponent,
    NAME_PATH,
    PATH_PREFERRED_GENDER_PRONOUN,
    STATUS_PATH,
    build_change_demographic_status_event,
    build_change_name_event,
    build_change_preferred_gender_pronoun_event,
)


def _make(connection, *, enable_mutations=False):
    return ADPWorkerDemographicToolsComponent(connection=connection, enable_mutations=enable_mutations)


def test_build_change_name_event_legal():
    path, body = build_change_name_event(
        name_type="legal", associate_oid="G3ABC",
        given_name="Jane", family_name="Doe",
    )
    assert path == NAME_PATH["legal"]
    legal = body["events"][0]["data"]["transform"]["worker"]["person"]["legalName"]
    assert legal == {"givenName": "Jane", "familyName1": "Doe"}


def test_build_change_name_event_preferred_paths():
    path, _body = build_change_name_event(name_type="preferred", associate_oid="G3ABC", given_name="J")
    assert path == NAME_PATH["preferred"]


def test_build_change_demographic_status_event_marital():
    path, body = build_change_demographic_status_event(
        status_type="marital", associate_oid="G3ABC", code_value="Married",
    )
    assert path == STATUS_PATH["marital"]
    person = body["events"][0]["data"]["transform"]["worker"]["person"]
    assert person["maritalStatusCode"] == {"statusCode": {"codeValue": "Married"}}


def test_build_change_demographic_status_event_military_classification():
    path, body = build_change_demographic_status_event(
        status_type="military_classification", associate_oid="G3ABC", code_value="Veteran",
    )
    assert path == STATUS_PATH["military_classification"]
    person = body["events"][0]["data"]["transform"]["worker"]["person"]
    assert person["militaryClassificationCode"] == {"statusCode": {"codeValue": "Veteran"}}


@pytest.mark.asyncio
async def test_build_tools_gated(adp_connection):
    c = _make(adp_connection, enable_mutations=False)
    assert await c.build_tools() == []


def test_build_change_preferred_gender_pronoun_event():
    body = build_change_preferred_gender_pronoun_event(
        associate_oid="G3ABC", pronoun_code="They/Them",
    )
    person = body["events"][0]["data"]["transform"]["worker"]["person"]
    assert person["preferredGenderPronounCode"] == {"codeValue": "They/Them"}


@pytest.mark.asyncio
async def test_tools_route_to_all_paths(adp_connection):
    c = _make(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"ok": True})
    with patch.object(c, "_post_event", new=mock_post):
        tools = {t.name: t for t in await c.build_tools()}
        assert set(tools.keys()) == {
            "change_employee_name",
            "change_employee_demographic_status",
            "change_employee_preferred_gender_pronoun",
        }
        await tools["change_employee_name"].ainvoke(
            {"name_type": "birth", "associate_oid": "A", "given_name": "Birth"},
        )
        await tools["change_employee_demographic_status"].ainvoke(
            {"status_type": "military_status", "associate_oid": "A", "code_value": "Active"},
        )
        await tools["change_employee_preferred_gender_pronoun"].ainvoke(
            {"associate_oid": "A", "pronoun_code": "She/Her"},
        )
    assert mock_post.call_args_list[0].kwargs["path"] == NAME_PATH["birth"]
    assert mock_post.call_args_list[1].kwargs["path"] == STATUS_PATH["military_status"]
    assert mock_post.call_args_list[2].kwargs["path"] == PATH_PREFERRED_GENDER_PRONOUN

"""Tests for ADPWorkerBiologicalToolsComponent."""

from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.adp.adp_worker_biological_tools import (
    ADPWorkerBiologicalToolsComponent,
    ATTR_PATH,
    PATH_BIRTH_DATE,
    build_change_biological_attribute_event,
    build_change_birth_date_event,
)


def _make(connection, *, enable_mutations=False):
    return ADPWorkerBiologicalToolsComponent(connection=connection, enable_mutations=enable_mutations)


def test_build_change_birth_date_event():
    body = build_change_birth_date_event(associate_oid="G3ABC", birth_date="1990-01-02")
    person = body["events"][0]["data"]["transform"]["worker"]["person"]
    assert person["birthDate"] == "1990-01-02"


def test_build_change_biological_attribute_event_gender():
    path, body = build_change_biological_attribute_event(
        attribute_type="gender", associate_oid="G3ABC", code_value="Male",
    )
    assert path == ATTR_PATH["gender"]
    person = body["events"][0]["data"]["transform"]["worker"]["person"]
    assert person["genderCode"] == {"codeValue": "Male"}


def test_build_change_biological_attribute_event_race():
    path, body = build_change_biological_attribute_event(
        attribute_type="race", associate_oid="G3ABC", code_value="Asian",
    )
    assert path == ATTR_PATH["race"]
    person = body["events"][0]["data"]["transform"]["worker"]["person"]
    assert person["raceCode"] == {"codeValue": "Asian"}


@pytest.mark.asyncio
async def test_build_tools_gated(adp_connection):
    c = _make(adp_connection, enable_mutations=False)
    assert await c.build_tools() == []


@pytest.mark.asyncio
async def test_tools_route_to_paths(adp_connection):
    c = _make(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"ok": True})
    with patch.object(c, "_post_event", new=mock_post):
        tools = {t.name: t for t in await c.build_tools()}
        await tools["change_employee_birth_date"].ainvoke(
            {"associate_oid": "A", "birth_date": "1990-01-01"},
        )
        await tools["change_employee_biological_attribute"].ainvoke(
            {"attribute_type": "gender_identity", "associate_oid": "A", "code_value": "NonBinary"},
        )
    assert mock_post.call_args_list[0].kwargs["path"] == PATH_BIRTH_DATE
    assert mock_post.call_args_list[1].kwargs["path"] == ATTR_PATH["gender_identity"]

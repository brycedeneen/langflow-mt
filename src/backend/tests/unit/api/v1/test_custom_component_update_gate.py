"""Regression coverage for the /custom_component/update RCE gate.

POST /api/v1/custom_component/update must not compile arbitrary user code
when LANGFLOW_ALLOW_CUSTOM_COMPONENTS is off and the caller is not a
platform admin. Covers
``docs/superpowers/specs/2026-04-26-custom-component-update-rce-gate-design.md``.
"""

from __future__ import annotations

import pytest
from langflow.services.deps import get_settings_service

from .conftest import login_as


@pytest.fixture
def restore_allow_custom():
    """Snapshot and restore settings.allow_custom_components for tests that mutate it."""
    settings = get_settings_service().settings
    original = settings.allow_custom_components
    yield settings
    settings.allow_custom_components = original


# Code with a unique marker name. The class's ``display_name`` is the proof
# signal — when this code is actually compiled and returned, the response's
# top-level ``display_name`` field reflects this distinctive marker rather
# than the canonical component's display_name (e.g. "Chat Input"). The
# rendered ``template`` field can't distinguish the two cases on its own
# because the handler echoes ``code_request.template`` into the response
# template, so ``inputs``/``outputs`` from the compiled class never surface
# there — ``display_name`` is the unambiguous signal.
USER_CODE_MARKER_DISPLAY_NAME = "TestUserCodeMarker"
USER_CODE_WITH_MARKER = f"""
from lfx.custom import CustomComponent
from lfx.io import StrInput, Output

class TestUserCodeMarker(CustomComponent):
    display_name = "{USER_CODE_MARKER_DISPLAY_NAME}"
    inputs = [StrInput(name="_unique_marker_input", display_name="Marker")]
    outputs = [Output(name="out", display_name="Out", method="build")]
    def build(self):
        return "user-code-ran"
"""

# A known canonical component type that ships with langflow. ChatInput is a
# stable choice because it's a foundational input component. Its canonical
# ``display_name`` is "Chat Input", which is what we expect to see when the
# gate substitutes registry code for the user payload.
CANONICAL_COMPONENT_TYPE = "ChatInput"
CANONICAL_DISPLAY_NAME = "Chat Input"


def _request_body(*, code: str, component_type: str | None = "ChatInput") -> dict:
    """Build a minimal /custom_component/update payload."""
    template: dict = {"code": {"value": code, "type": "code"}}
    if component_type is not None:
        template["_type"] = component_type
    return {
        "code": code,
        "field": "code",
        "field_value": code,
        "template": template,
        "tool_mode": False,
    }


async def test_canonical_code_used_when_gate_closed(client, tenant_and_admin, restore_allow_custom):
    """Gate closed (default), normal tenant user.

    Submit attacker code with a valid template._type. Response must reflect
    canonical component, not the attacker code.
    """
    settings = restore_allow_custom
    settings.allow_custom_components = False  # Default; explicit for clarity.

    headers = await login_as(client, tenant_and_admin["tenant_username"])
    response = await client.post(
        "api/v1/custom_component/update",
        headers=headers,
        json=_request_body(code=USER_CODE_WITH_MARKER, component_type=CANONICAL_COMPONENT_TYPE),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    # When the gate fires, the handler swaps ``code_request.code`` for the
    # registry's canonical source for ``ChatInput``. The compiled component's
    # ``display_name`` ("Chat Input") therefore lands on ``component_node`` —
    # NOT the attacker class's ``display_name`` ("TestUserCodeMarker").
    assert body.get("display_name") == CANONICAL_DISPLAY_NAME, (
        f"Expected canonical display_name {CANONICAL_DISPLAY_NAME!r}; "
        f"got {body.get('display_name')!r} (user code was likely compiled)"
    )
    assert body.get("display_name") != USER_CODE_MARKER_DISPLAY_NAME, (
        f"User code was compiled despite gate; display_name={body.get('display_name')!r}"
    )


async def test_400_when_template_type_missing_and_gate_closed(client, tenant_and_admin, restore_allow_custom):
    """Gate closed, normal user, no template._type. Must 400 with the missing-id message."""
    settings = restore_allow_custom
    settings.allow_custom_components = False

    headers = await login_as(client, tenant_and_admin["tenant_username"])
    response = await client.post(
        "api/v1/custom_component/update",
        headers=headers,
        json=_request_body(code=USER_CODE_WITH_MARKER, component_type=None),
    )

    assert response.status_code == 400, response.text
    assert "template._type" in response.json().get("detail", ""), response.text


async def test_403_when_template_type_unknown_and_gate_closed(client, tenant_and_admin, restore_allow_custom):
    """Gate closed, normal user, unknown template._type. Must 403 with unknown-type message."""
    settings = restore_allow_custom
    settings.allow_custom_components = False

    headers = await login_as(client, tenant_and_admin["tenant_username"])
    response = await client.post(
        "api/v1/custom_component/update",
        headers=headers,
        json=_request_body(
            code=USER_CODE_WITH_MARKER,
            component_type="ComponentTypeThatDoesNotExist",
        ),
    )

    assert response.status_code == 403, response.text
    assert "ComponentTypeThatDoesNotExist" in response.json().get("detail", ""), response.text


async def test_user_code_used_when_global_flag_open(client, tenant_and_admin, restore_allow_custom):
    """Gate OPEN at deployment level (allow_custom_components=True).

    Normal user. User-supplied marker code must be compiled.
    """
    settings = restore_allow_custom
    settings.allow_custom_components = True

    headers = await login_as(client, tenant_and_admin["tenant_username"])
    response = await client.post(
        "api/v1/custom_component/update",
        headers=headers,
        json=_request_body(code=USER_CODE_WITH_MARKER, component_type="TestUserCodeMarker"),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    # Gate is open at the deployment level — user-supplied code must be
    # compiled, so the response's ``display_name`` reflects the marker class.
    assert body.get("display_name") == USER_CODE_MARKER_DISPLAY_NAME, (
        f"Expected user marker display_name {USER_CODE_MARKER_DISPLAY_NAME!r}; got {body.get('display_name')!r}"
    )


async def test_user_code_used_when_platform_admin(client, tenant_and_admin, restore_allow_custom):
    """Gate closed at deployment level, but caller is platform admin.

    User-supplied code must still be compiled (admin override).
    """
    from langflow.services.database.models.user.model import User
    from langflow.services.deps import session_scope
    from sqlmodel import select

    settings = restore_allow_custom
    settings.allow_custom_components = False

    # Promote the tenant user to platform admin for this test.
    async with session_scope() as session:
        result = await session.exec(select(User).where(User.id == tenant_and_admin["tenant_id"]))
        user = result.one()
        original_flag = user.is_platform_admin
        user.is_platform_admin = True
        session.add(user)
        await session.commit()

    try:
        headers = await login_as(client, tenant_and_admin["tenant_username"])
        response = await client.post(
            "api/v1/custom_component/update",
            headers=headers,
            json=_request_body(code=USER_CODE_WITH_MARKER, component_type="TestUserCodeMarker"),
        )
    finally:
        async with session_scope() as session:
            result = await session.exec(select(User).where(User.id == tenant_and_admin["tenant_id"]))
            user = result.one()
            user.is_platform_admin = original_flag
            session.add(user)
            await session.commit()

    assert response.status_code == 200, response.text
    body = response.json()
    # Caller is a platform admin — user-supplied code must be compiled even
    # with the deployment-level flag closed. Marker display_name proves it.
    assert body.get("display_name") == USER_CODE_MARKER_DISPLAY_NAME, (
        f"Expected user marker display_name {USER_CODE_MARKER_DISPLAY_NAME!r}; got {body.get('display_name')!r}"
    )

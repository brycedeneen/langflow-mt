import pytest
from fastapi import HTTPException

from langflow.api.utils.authz import ROLE_ORDER, assert_org_role
from langflow.services.database.models.membership.model import MembershipRole


def _fake_user(is_platform_admin: bool = False):
    _is_platform_admin = is_platform_admin

    class U:
        id = "u"
        is_platform_admin = _is_platform_admin
    return U()


@pytest.mark.parametrize(
    "role,min_role,allowed",
    [
        (MembershipRole.OWNER,    MembershipRole.VIEWER,   True),
        (MembershipRole.VIEWER,   MembershipRole.OWNER,    False),
        (MembershipRole.MEMBER,   MembershipRole.MEMBER,   True),
        (MembershipRole.OPERATOR, MembershipRole.MEMBER,   False),
        (MembershipRole.OPERATOR, MembershipRole.OPERATOR, True),
        (MembershipRole.ADMIN,    MembershipRole.MEMBER,   True),
    ],
)
def test_role_order_threshold(role, min_role, allowed):
    assert (ROLE_ORDER[role] >= ROLE_ORDER[min_role]) is allowed


async def test_assert_org_role_403_when_no_membership(mocker):
    mocker.patch(
        "langflow.api.utils.authz._load_membership",
        return_value=None,
    )
    with pytest.raises(HTTPException) as exc:
        await assert_org_role(_fake_user(), "org-1", MembershipRole.VIEWER, session=object())
    assert exc.value.status_code == 403


async def test_assert_org_role_bypasses_for_platform_admin(mocker):
    mocker.patch(
        "langflow.api.utils.authz._load_membership",
        return_value=None,
    )
    # Platform admins bypass even when no membership exists.
    result = await assert_org_role(
        _fake_user(is_platform_admin=True),
        "org-1",
        MembershipRole.OWNER,
        session=object(),
    )
    assert result is None


async def test_assert_org_role_returns_membership_on_success(mocker):
    class M:
        role = MembershipRole.ADMIN
    mocker.patch("langflow.api.utils.authz._load_membership", return_value=M())
    result = await assert_org_role(_fake_user(), "org-1", MembershipRole.MEMBER, session=object())
    assert result.role == MembershipRole.ADMIN


async def test_assert_org_role_403_when_role_too_low(mocker):
    class M:
        role = MembershipRole.VIEWER
    mocker.patch("langflow.api.utils.authz._load_membership", return_value=M())
    with pytest.raises(HTTPException) as exc:
        await assert_org_role(_fake_user(), "org-1", MembershipRole.MEMBER, session=object())
    assert exc.value.status_code == 403

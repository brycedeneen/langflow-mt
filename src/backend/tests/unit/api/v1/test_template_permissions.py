"""Unit tests for user_can_edit_template permission helper.

These tests use lightweight fake User/Template objects — no DB required.
"""

from __future__ import annotations

from uuid import uuid4

from langflow.api.v1._template_permissions import user_can_edit_template


def _make_user(*, id=None, is_platform_admin=False, org_admin_of=None):
    class _U:
        def __init__(self):
            self.id = id or uuid4()
            self.is_platform_admin = is_platform_admin
            self._org_admin_of = set(org_admin_of or [])

        def is_org_admin(self, org_id):
            return org_id in self._org_admin_of

    return _U()


def _make_template(*, scope="platform", org_id=None, created_by=None):
    class _T:
        pass

    t = _T()
    t.scope = scope
    t.org_id = org_id
    t.created_by = created_by
    return t


def test_platform_admin_can_edit_any():
    u = _make_user(is_platform_admin=True)
    assert user_can_edit_template(u, _make_template()) is True
    assert user_can_edit_template(u, _make_template(scope="org", org_id=uuid4())) is True


def test_non_admin_cannot_edit_platform():
    u = _make_user()
    assert user_can_edit_template(u, _make_template()) is False


def test_org_admin_can_edit_own_org_template():
    org = uuid4()
    u = _make_user(org_admin_of=[org])
    assert user_can_edit_template(u, _make_template(scope="org", org_id=org)) is True


def test_creator_can_edit_own_org_template():
    uid = uuid4()
    org = uuid4()
    u = _make_user(id=uid)
    t = _make_template(scope="org", org_id=org, created_by=uid)
    assert user_can_edit_template(u, t) is True


def test_other_member_cannot_edit():
    org = uuid4()
    u = _make_user()
    t = _make_template(scope="org", org_id=org, created_by=uuid4())
    assert user_can_edit_template(u, t) is False

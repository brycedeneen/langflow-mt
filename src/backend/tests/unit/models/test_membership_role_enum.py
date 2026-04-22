from langflow.services.database.models.membership.model import MembershipRole


def test_membership_role_contains_all_five_tiers():
    assert {r.value for r in MembershipRole} == {
        "owner", "admin", "member", "operator", "viewer"
    }


def test_membership_role_owner_value_unchanged():
    # Backward compatibility — existing rows use this string.
    assert MembershipRole.OWNER.value == "owner"

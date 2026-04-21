"""Permission helper for Template edit operations.

Usage::

    from langflow.api.v1._template_permissions import user_can_edit_template

    if not user_can_edit_template(current_user, template_row):
        raise HTTPException(status_code=403, detail="Forbidden")

Notes
-----
``user.is_org_admin(org_id)`` is called when present.  The real ``User`` model
does not yet carry this method; callers that need org-admin semantics must
attach it (or a compatible shim) before invoking this helper.  When the method
is absent the helper falls through to the creator check.
"""

from __future__ import annotations


def user_can_edit_template(user, template) -> bool:
    """Return True when *user* is allowed to mutate *template*.

    Decision order:
    1. Platform admins may edit anything.
    2. ``scope == "platform"`` templates require platform-admin status (denied here).
    3. Org-scoped templates with no ``org_id`` are denied (data inconsistency).
    4. Org admins of the owning org may edit.
    5. The original creator may edit their own org-scoped template.
    """
    if getattr(user, "is_platform_admin", False):
        return True
    if template.scope == "platform":
        return False
    if template.org_id is None:
        return False
    if hasattr(user, "is_org_admin") and user.is_org_admin(template.org_id):
        return True
    return template.created_by == user.id

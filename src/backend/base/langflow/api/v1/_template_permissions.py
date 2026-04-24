"""Permission helper for Template edit operations.

Usage::

    from langflow.api.v1._template_permissions import user_can_edit_template

    if not user_can_edit_template(current_user, template_row):
        raise HTTPException(status_code=403, detail="Forbidden")
"""

from __future__ import annotations


def user_can_edit_template(user, template) -> bool:
    """Return True when *user* is allowed to mutate *template*.

    Decision order:
    1. Platform admins may edit anything.
    2. ``scope == "platform"`` templates require platform-admin status (denied here).
    3. Org-scoped templates with no ``org_id`` are denied (data inconsistency).
    4. The original creator may edit their own org-scoped template.
    """
    if getattr(user, "is_platform_admin", False):
        return True
    if template.scope == "platform":
        return False
    if template.org_id is None:
        return False
    return template.created_by == user.id

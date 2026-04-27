def test_notification_category_includes_flow_error():
    from langflow.services.database.models.admin_notification import NotificationCategory

    assert NotificationCategory.FLOW_ERROR.value == "flow_error"
    assert len(NotificationCategory.FLOW_ERROR.value) <= 32  # column constraint


def test_notification_severity_includes_error():
    from langflow.services.database.models.admin_notification import NotificationSeverity

    assert NotificationSeverity.ERROR.value == "error"
    assert len(NotificationSeverity.ERROR.value) <= 16


def test_usage_alert_event_accepts_flow_error_and_error():
    from uuid import uuid4
    from langflow.services.notifier.protocol import UsageAlertEvent

    event = UsageAlertEvent(
        category="flow_error",
        severity="error",
        org_id=uuid4(),
        title="t",
        body_md="b",
        metadata={},
    )
    assert event.category == "flow_error"
    assert event.severity == "error"


def test_notification_category_literal_matches_enum():
    """Drift guard: protocol Literal must mirror the model enum exactly."""
    from typing import get_args

    from langflow.services.database.models.admin_notification import NotificationCategory
    from langflow.services.notifier.protocol import NotificationCategoryValue

    assert set(get_args(NotificationCategoryValue)) == {m.value for m in NotificationCategory}


def test_notification_severity_literal_matches_enum():
    """Drift guard: protocol Literal must mirror the model enum exactly."""
    from typing import get_args

    from langflow.services.database.models.admin_notification import NotificationSeverity
    from langflow.services.notifier.protocol import NotificationSeverityValue

    assert set(get_args(NotificationSeverityValue)) == {m.value for m in NotificationSeverity}

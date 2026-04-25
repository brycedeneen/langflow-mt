from langflow.services.database.models.admin_notification.model import (
    NotificationAudience,
    NotificationCategory,
)


def test_notification_audience_has_platform_admin():
    assert NotificationAudience.PLATFORM_ADMIN.value == "platform_admin"


def test_notification_category_has_pro_services():
    assert NotificationCategory.PROFESSIONAL_SERVICES_REQUEST.value == "professional_services_request"


def test_component_metadata_has_integration_minutes_columns():
    from langflow.services.database.models.component_metadata.model import ComponentMetadata
    cols = ComponentMetadata.__table__.columns
    assert "integration_minutes_low" in cols
    assert "integration_minutes_high" in cols


def test_flow_has_ps_request_active():
    from langflow.services.database.models.flow.model import Flow
    assert "ps_request_active" in Flow.__table__.columns


def test_organization_has_billable_rate_columns():
    from langflow.services.database.models.organization.model import Organization
    cols = Organization.__table__.columns
    assert "billable_rate_low_per_hour" in cols
    assert "billable_rate_high_per_hour" in cols


def test_admin_notification_has_audience_user_id():
    from langflow.services.database.models.admin_notification.model import AdminNotification
    assert "audience_user_id" in AdminNotification.__table__.columns

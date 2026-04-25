from decimal import Decimal

from langflow.services.database.models.professional_services_settings.model import (
    ProfessionalServicesSettings,
)


def test_settings_singleton_id_is_one():
    settings = ProfessionalServicesSettings(
        default_hourly_rate_low=Decimal("200.00"),
        default_hourly_rate_high=Decimal("200.00"),
    )
    assert settings.id == 1


def test_settings_optional_webhook_fields():
    settings = ProfessionalServicesSettings()
    assert settings.webhook_url is None
    assert settings.webhook_secret_encrypted is None

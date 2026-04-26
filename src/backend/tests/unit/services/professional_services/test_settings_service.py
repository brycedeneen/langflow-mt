from decimal import Decimal
from uuid import uuid4

from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.professional_services_settings.model import (
    ProfessionalServicesSettings,
)
from langflow.services.professional_services.settings_service import (
    RateBand,
    resolve_rate_band,
)


def test_resolve_rate_band_uses_org_override():
    org = Organization(
        id=uuid4(),
        name="Acme",
        slug="acme",
        billable_rate_low_per_hour=Decimal("150.00"),
        billable_rate_high_per_hour=Decimal("180.00"),
    )
    settings = ProfessionalServicesSettings(
        default_hourly_rate_low=Decimal("200.00"),
        default_hourly_rate_high=Decimal("200.00"),
    )
    band = resolve_rate_band(org, settings)
    assert band == RateBand(low=Decimal("150.00"), high=Decimal("180.00"))


def test_resolve_rate_band_falls_back_to_global():
    org = Organization(id=uuid4(), name="Acme", slug="acme")
    settings = ProfessionalServicesSettings(
        default_hourly_rate_low=Decimal("200.00"),
        default_hourly_rate_high=Decimal("200.00"),
    )
    band = resolve_rate_band(org, settings)
    assert band == RateBand(low=Decimal("200.00"), high=Decimal("200.00"))


def test_resolve_rate_band_returns_nones_when_unset():
    org = Organization(id=uuid4(), name="Acme", slug="acme")
    settings = ProfessionalServicesSettings()
    band = resolve_rate_band(org, settings)
    assert band == RateBand(low=None, high=None)

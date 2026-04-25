from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlmodel import Session, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.professional_services_settings.model import (
    ProfessionalServicesSettings,
)


@dataclass(frozen=True)
class RateBand:
    low: Decimal | None
    high: Decimal | None


def resolve_rate_band(
    org: Organization, settings: ProfessionalServicesSettings
) -> RateBand:
    """Org override wins; falls back to global default; both can be None."""
    low = org.billable_rate_low_per_hour or settings.default_hourly_rate_low
    high = org.billable_rate_high_per_hour or settings.default_hourly_rate_high
    return RateBand(low=low, high=high)


def read_settings_singleton(session: Session) -> ProfessionalServicesSettings:
    """Returns the settings singleton; the migration seeded id=1 so this never raises."""
    settings = session.exec(
        select(ProfessionalServicesSettings).where(ProfessionalServicesSettings.id == 1)
    ).one()
    return settings


async def read_settings_singleton_async(
    session: AsyncSession,
) -> ProfessionalServicesSettings:
    """Async equivalent of ``read_settings_singleton``.

    The migration seeds id=1 so this never raises in normal operation. Tests
    that bootstrap via ``SQLModel.metadata.create_all`` must seed the row in
    a session-scoped fixture (see ``tests/unit/api/v1/conftest.py``).
    """
    row = (
        await session.exec(
            select(ProfessionalServicesSettings).where(
                ProfessionalServicesSettings.id == 1
            )
        )
    ).one()
    return row

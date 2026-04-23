from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from langflow.services.pricing.service import PricingService

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class PricingServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(PricingService)

    def create(self, settings_service: "SettingsService") -> PricingService:
        return PricingService.from_settings(settings_service.settings)

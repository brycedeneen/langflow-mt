from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from langflow.services.factory import ServiceFactory
from langflow.services.redis.service import RedisService

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class RedisServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(RedisService)

    @override
    def create(self, settings_service: SettingsService) -> RedisService:
        return RedisService(url=settings_service.settings.redis_url)

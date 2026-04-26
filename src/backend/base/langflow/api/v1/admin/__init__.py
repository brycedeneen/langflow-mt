"""Admin-gated API endpoints."""

from fastapi import APIRouter

from .alert_rules import router as _alert_rules_router
from .audit_logs import router as _audit_logs_router
from .metadata import router as _metadata_router
from .notifications import router as _notifications_router
from .orgs import router as _orgs_router
from .professional_services_settings import router as _professional_services_settings_router
from .tags import router as _tags_router
from .usage_thresholds import router as _usage_thresholds_router
from .users import router as _users_router

router = APIRouter(prefix="/admin", tags=["Admin"])
router.include_router(_orgs_router)
router.include_router(_metadata_router)
router.include_router(_users_router)
router.include_router(_audit_logs_router)
router.include_router(_notifications_router)
router.include_router(_usage_thresholds_router)
router.include_router(_alert_rules_router)
router.include_router(_tags_router)
router.include_router(_professional_services_settings_router)

__all__ = ["router"]

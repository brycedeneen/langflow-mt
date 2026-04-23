"""Admin-gated API endpoints."""

from fastapi import APIRouter

from .audit_logs import router as _audit_logs_router
from .metadata import router as _metadata_router
from .orgs import router as _orgs_router
from .users import router as _users_router

router = APIRouter(prefix="/admin", tags=["Admin"])
router.include_router(_orgs_router)
router.include_router(_metadata_router)
router.include_router(_users_router)
router.include_router(_audit_logs_router)

__all__ = ["router"]

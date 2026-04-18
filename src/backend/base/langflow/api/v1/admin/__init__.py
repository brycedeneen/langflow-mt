"""Admin-gated API endpoints."""

from fastapi import APIRouter

from .metadata import router as _metadata_router
from .orgs import router as _orgs_router

router = APIRouter(prefix="/admin", tags=["Admin"])
router.include_router(_orgs_router)
router.include_router(_metadata_router)

__all__ = ["router"]

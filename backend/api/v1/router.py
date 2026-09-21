"""Aggregates every v1 endpoint router."""

from fastapi import APIRouter

from api.v1.admin.router import router as admin_router
from api.v1.endpoints import (
    assistant,
    auth,
    catalog,
    estimates,
    facets,
    listings,
    me,
    models,
    search,
)

router = APIRouter()
router.include_router(search.router)
router.include_router(listings.router)
router.include_router(facets.router)
router.include_router(models.router)
router.include_router(catalog.router)
router.include_router(estimates.router)
router.include_router(assistant.router)
router.include_router(auth.router)
router.include_router(me.router)
router.include_router(admin_router)

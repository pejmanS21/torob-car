"""Aggregates every v1 endpoint router."""

from fastapi import APIRouter

from api.v1.endpoints import facets, listings, search

router = APIRouter()
router.include_router(search.router)
router.include_router(listings.router)
router.include_router(facets.router)

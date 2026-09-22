import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from dependencies.providers import get_listing_service
from schemas.listing import ListingCard, ListingDetail
from services.listing_service import ListingService

DEFAULT_SIMILAR_LIMIT = 6
MAX_SIMILAR_LIMIT = 20

router = APIRouter(prefix="/listings", tags=["listings"])
ServiceDep = Annotated[ListingService, Depends(get_listing_service)]


@router.get("")
async def read_listings(
    service: ServiceDep, ids: Annotated[list[uuid.UUID], Query(min_length=1)]
) -> list[ListingCard]:
    return await service.get_many(ids)


@router.get("/{listing_id}")
async def read_listing(service: ServiceDep, listing_id: uuid.UUID) -> ListingDetail:
    return await service.get_detail(listing_id)


@router.get("/{listing_id}/similar")
async def read_similar_listings(
    service: ServiceDep,
    listing_id: uuid.UUID,
    limit: Annotated[int, Query(ge=1, le=MAX_SIMILAR_LIMIT)] = DEFAULT_SIMILAR_LIMIT,
) -> list[ListingCard]:
    return await service.get_similar(listing_id, limit)

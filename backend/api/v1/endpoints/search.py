from typing import Annotated

from fastapi import APIRouter, Depends, Query

from dependencies.providers import get_search_service
from schemas.search import SearchParams, SearchResponse
from services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search_listings(
    service: Annotated[SearchService, Depends(get_search_service)],
    params: Annotated[SearchParams, Query()],
) -> SearchResponse:
    return await service.search(params.q, params, params.page, params.page_size)

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from dependencies.providers import get_facet_service
from schemas.facets import Facets
from schemas.search import SearchParams
from services.facet_service import FacetService

router = APIRouter(prefix="/facets", tags=["facets"])


@router.get("", response_model=Facets)
async def read_facets(
    service: Annotated[FacetService, Depends(get_facet_service)],
    params: Annotated[SearchParams, Query()],
) -> Facets:
    """Same parameters as GET /search, so the panel counts follow the search."""
    return await service.get_facets(params.q, params)

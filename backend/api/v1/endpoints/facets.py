from typing import Annotated

from fastapi import APIRouter, Depends

from dependencies.providers import get_facet_service
from enums import Category
from schemas.facets import Facets
from services.facet_service import FacetService

router = APIRouter(prefix="/facets", tags=["facets"])


@router.get("", response_model=Facets)
async def read_facets(
    service: Annotated[FacetService, Depends(get_facet_service)],
    category: Category | None = None,
) -> Facets:
    return await service.get_facets(category)

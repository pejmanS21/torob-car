from typing import Annotated

from fastapi import APIRouter, Depends, Query

from dependencies.providers import get_catalog_service
from enums import Category
from schemas.catalog import CatalogSuggestion
from services.catalog_service import CatalogService

MAX_SUGGEST_QUERY_LENGTH = 100

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/suggest", response_model=list[CatalogSuggestion])
async def suggest_vehicles(
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    q: Annotated[str | None, Query(max_length=MAX_SUGGEST_QUERY_LENGTH)] = None,
    category: Category | None = None,
) -> list[CatalogSuggestion]:
    return await service.suggest(q, category)

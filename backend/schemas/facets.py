from datetime import datetime

from pydantic import BaseModel

from enums import Category


class FacetCount(BaseModel):
    value: str
    count: int


class ModelFacet(BaseModel):
    brand: str
    model: str
    count: int


class Facets(BaseModel):
    categories: dict[Category, int]
    models: list[ModelFacet]
    cities: list[FacetCount]
    model_count: int
    data_as_of: datetime | None

from pydantic import BaseModel

from enums import Category


class CatalogSuggestion(BaseModel):
    brand: str
    model: str
    trim: str
    category: Category
    count: int

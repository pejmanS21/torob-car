import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

MAX_IMPORT_SAVED = 500
MAX_IMPORT_ALERTS = 50
MAX_ALERT_TITLE_LENGTH = 200


class PriceAlertCreate(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_ALERT_TITLE_LENGTH)
    threshold: int = Field(gt=0)
    # The frontend's search parameters, stored as sent and never interpreted here.
    params: dict[str, Any]


class PriceAlertRead(PriceAlertCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


class ImportRequest(BaseModel):
    saved: Annotated[list[uuid.UUID], Field(max_length=MAX_IMPORT_SAVED)]
    alerts: Annotated[list[PriceAlertCreate], Field(max_length=MAX_IMPORT_ALERTS)]


class AccountState(BaseModel):
    saved: list[uuid.UUID]
    alerts: list[PriceAlertRead]

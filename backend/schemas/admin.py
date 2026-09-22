import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from enums import AdminAction, UserRole
from schemas.auth import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH

MAX_PAGE_SIZE = 100


class AdminUserRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class AdminUserDetail(AdminUserRow):
    saved_count: int
    alert_count: int


class AdminUserPage(BaseModel):
    items: list[AdminUserRow]
    total: int


class AdminUserUpdate(BaseModel):
    """Both fields optional: a request may change activity, role, or both."""

    is_active: bool | None = None
    role: UserRole | None = None


class AdminPasswordReset(BaseModel):
    new: Annotated[
        SecretStr, Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
    ]


class AuditRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_email: str
    action: AdminAction
    target_type: str
    target_id: str | None
    summary: dict[str, Any]
    created_at: datetime


class AuditPage(BaseModel):
    items: list[AuditRow]
    total: int


class AdminStats(BaseModel):
    users_total: int
    users_active: int
    admins_active: int
    listings_total: int
    newest_listing_fetched_at: datetime | None
    recent_audit: list[AuditRow]

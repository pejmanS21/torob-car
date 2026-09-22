import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, UUIDPrimaryKeyMixin, enum_type
from enums import AdminAction
from models.user import EMAIL_MAX_LENGTH, utc_now


class AdminAudit(UUIDPrimaryKeyMixin, Base):
    """Append-only. There is no update or delete path anywhere in the codebase, and
    rows are written in the same transaction as the change they describe."""

    __tablename__ = "admin_audit"

    # SET NULL, never CASCADE: deleting an admin must not erase their history.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    # Denormalised so the row stays readable after the actor is deleted.
    actor_email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH))
    action: Mapped[AdminAction] = mapped_column(enum_type(AdminAction), index=True)
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )

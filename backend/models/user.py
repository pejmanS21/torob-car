from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, UUIDPrimaryKeyMixin, enum_type
from enums import UserRole

EMAIL_MAX_LENGTH = 320


def utc_now() -> datetime:
    return datetime.now(UTC)


class User(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "users"

    # Always stored lowercased (schemas/auth.py normalises), so uniqueness is
    # case-insensitive without a functional index.
    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[UserRole] = mapped_column(enum_type(UserRole), default=UserRole.USER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Copied into every token as `ver`; bumping it revokes all of the user's tokens.
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

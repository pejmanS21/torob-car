from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, UUIDPrimaryKeyMixin


class AnonymousChatQuota(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "anonymous_chat_quotas"

    identity: Mapped[str] = mapped_column(String(64), unique=True)
    count: Mapped[int]
    resets_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

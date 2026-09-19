from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, UUIDPrimaryKeyMixin


class City(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "cities"

    name: Mapped[str] = mapped_column(String(128), unique=True)
    name_normalized: Mapped[str] = mapped_column(String(128), index=True)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    listing_count: Mapped[int] = mapped_column(Integer, default=0)

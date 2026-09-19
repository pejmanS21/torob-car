import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, UUIDPrimaryKeyMixin, enum_type
from enums import BodyCondition, Category, EstimateBasis, Fuel, Gearbox
from models.city import City
from models.vehicle_catalog import VehicleCatalog


class Listing(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "listings"
    __table_args__ = (
        Index("ix_listings_category_catalog", "category", "catalog_id"),
        Index(
            "ix_listings_title_trgm",
            "title_normalized",
            postgresql_using="gin",
            postgresql_ops={"title_normalized": "gin_trgm_ops"},
        ),
    )

    token: Mapped[str] = mapped_column(String(64), unique=True)
    url: Mapped[str] = mapped_column(Text)
    category: Mapped[Category] = mapped_column(enum_type(Category))
    catalog_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vehicle_catalog.id")
    )
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id"), index=True)

    title: Mapped[str] = mapped_column(Text)
    title_normalized: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)

    year: Mapped[int | None] = mapped_column(Integer)
    km: Mapped[int | None] = mapped_column(Integer)
    price: Mapped[int | None] = mapped_column(BigInteger)  # toman
    gearbox: Mapped[Gearbox | None] = mapped_column(enum_type(Gearbox))
    fuel: Mapped[Fuel | None] = mapped_column(enum_type(Fuel))
    color: Mapped[str | None] = mapped_column(String(64))
    body_condition: Mapped[BodyCondition | None] = mapped_column(
        enum_type(BodyCondition)
    )
    insurance_months: Mapped[int | None] = mapped_column(Integer)
    vehicle_type: Mapped[str | None] = mapped_column(String(64))
    is_dealer: Mapped[bool] = mapped_column(Boolean, default=False)

    district: Mapped[str | None] = mapped_column(String(128))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    image_urls: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    thumbnail_urls: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    est_price: Mapped[int | None] = mapped_column(BigInteger)
    est_basis: Mapped[EstimateBasis] = mapped_column(
        enum_type(EstimateBasis), default=EstimateBasis.NONE
    )
    est_sample_size: Mapped[int] = mapped_column(Integer, default=0)
    km_factor: Mapped[float] = mapped_column(Float, default=1.0)
    insurance_factor: Mapped[float] = mapped_column(Float, default=1.0)
    diff_pct: Mapped[float | None] = mapped_column(Float)
    deal_score: Mapped[int | None] = mapped_column(Integer)
    price_suspect: Mapped[bool] = mapped_column(Boolean, default=False)

    # lazy="raise": async sessions cannot lazy-load; repositories must join explicitly.
    city: Mapped[City] = relationship(lazy="raise")
    catalog: Mapped[VehicleCatalog | None] = relationship(lazy="raise")

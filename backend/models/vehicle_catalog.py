from sqlalchemy import Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, UUIDPrimaryKeyMixin, enum_type
from enums import Category


class VehicleCatalog(UUIDPrimaryKeyMixin, Base):
    """One row per distinct Divar «برند و مدل» string. `trim` is the raw string;
    `brand` and `model` are normalised (see ingest.normalizers.split_brand_model)."""

    __tablename__ = "vehicle_catalog"
    __table_args__ = (
        UniqueConstraint("category", "trim", name="uq_vehicle_catalog_category_trim"),
        Index(
            "ix_vehicle_catalog_trim_trgm",
            "trim_normalized",
            postgresql_using="gin",
            postgresql_ops={"trim_normalized": "gin_trgm_ops"},
        ),
    )

    category: Mapped[Category] = mapped_column(enum_type(Category))
    brand: Mapped[str] = mapped_column(String(128), index=True)
    model: Mapped[str] = mapped_column(String(192))
    trim: Mapped[str] = mapped_column(String(255))
    trim_normalized: Mapped[str] = mapped_column(String(255))
    listing_count: Mapped[int] = mapped_column(Integer, default=0)

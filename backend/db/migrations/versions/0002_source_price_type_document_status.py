"""add source, price type and document status

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCE = sa.Enum(
    "divar",
    "bama",
    "karnameh",
    "hamrah_mechanic",
    name="source",
    native_enum=False,
    length=32,
)
_PRICE_TYPE = sa.Enum(
    "lumpsum",
    "negotiable",
    "installment",
    name="pricetype",
    native_enum=False,
    length=32,
)
_DOCUMENT_STATUS = sa.Enum(
    "title_in_name",
    "ready_to_transfer",
    "white_title",
    "no_title",
    "mortgaged",
    "single_page",
    "two_page",
    "multi_page",
    name="documentstatus",
    native_enum=False,
    length=32,
)


def upgrade() -> None:
    # server_default backfills rows ingested before multi-source support: they are Divar's.
    op.add_column(
        "listings",
        sa.Column("source", _SOURCE, nullable=False, server_default="divar"),
    )
    op.add_column("listings", sa.Column("price_type", _PRICE_TYPE, nullable=True))
    op.add_column(
        "listings", sa.Column("document_status", _DOCUMENT_STATUS, nullable=True)
    )
    op.create_index(op.f("ix_listings_source"), "listings", ["source"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_listings_source"), table_name="listings")
    op.drop_column("listings", "document_status")
    op.drop_column("listings", "price_type")
    op.drop_column("listings", "source")

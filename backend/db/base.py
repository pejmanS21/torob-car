import uuid
from enum import StrEnum

from sqlalchemy import Enum, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from db.ids import new_uuid8

ENUM_COLUMN_LENGTH = 32


class Base(DeclarativeBase):
    pass


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),  # native `uuid` column on Postgres
        primary_key=True,
        default=new_uuid8,  # generated app-side, never server_default
    )


def enum_type(enum_class: type[StrEnum]) -> Enum:
    """VARCHAR-backed enum that stores `.value`. Not a native Postgres enum, so
    adding a member never needs a migration."""
    return Enum(
        enum_class,
        native_enum=False,
        length=ENUM_COLUMN_LENGTH,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
)

from enums import UserRole

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128  # bounds the work an attacker can force on the hasher


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


# EmailStr lowercases only the domain; the whole address is lowered so that
# `users.email` uniqueness is case-insensitive.
Email = Annotated[EmailStr, BeforeValidator(_strip), AfterValidator(str.lower)]
NewPassword = Annotated[
    SecretStr, Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
]
# No minimum: a too-short guess must fail as 401 invalid_credentials, not 422.
GivenPassword = Annotated[SecretStr, Field(max_length=MAX_PASSWORD_LENGTH)]


class UserCreate(BaseModel):
    email: Email
    password: NewPassword


class LoginRequest(BaseModel):
    email: Email
    password: GivenPassword


class PasswordChange(BaseModel):
    current: GivenPassword
    new: NewPassword


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: UserRole
    created_at: datetime

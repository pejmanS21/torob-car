import pytest
from pydantic import ValidationError

from schemas.auth import LoginRequest, PasswordChange, UserCreate


def test_email_is_stripped_and_lowercased() -> None:
    account = UserCreate(email="  Reader@Example.COM ", password="12345678")
    assert account.email == "reader@example.com"
    assert LoginRequest(email="READER@example.com", password="x").email == (
        "reader@example.com"
    )


@pytest.mark.parametrize("password", ["1234567", "x" * 129])
def test_new_passwords_must_be_8_to_128_characters(password: str) -> None:
    with pytest.raises(ValidationError):
        UserCreate(email="reader@example.com", password=password)
    with pytest.raises(ValidationError):
        PasswordChange(current="whatever", new=password)


def test_login_accepts_a_short_password_so_it_fails_as_401_not_422() -> None:
    assert LoginRequest(email="reader@example.com", password="x")
    with pytest.raises(ValidationError):
        LoginRequest(email="reader@example.com", password="x" * 129)


def test_passwords_never_appear_in_repr() -> None:
    account = UserCreate(email="reader@example.com", password="hunter2-hunter2")
    assert "hunter2" not in repr(account)


def test_a_malformed_email_is_rejected() -> None:
    with pytest.raises(ValidationError):
        UserCreate(email="not-an-email", password="12345678")

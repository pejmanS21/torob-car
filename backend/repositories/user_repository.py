import uuid

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from enums import UserRole
from models.user import User, utc_now


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        return await self._session.scalar(select(User).where(User.email == email))

    async def create_if_absent(
        self, email: str, password_hash: str, role: UserRole
    ) -> User | None:
        """One atomic statement, so two concurrent sign-ups (or two workers
        bootstrapping the admin) cannot both win. `None` = the email is taken."""
        statement = (
            insert(User)
            .values(email=email, password_hash=password_hash, role=role)
            .on_conflict_do_nothing(index_elements=[User.email])
            .returning(User)
        )
        return await self._session.scalar(statement)

    async def record_login(self, user: User) -> None:
        user.last_login_at = utc_now()
        await self._session.flush()

    async def replace_password(self, user: User, password_hash: str) -> None:
        user.password_hash = password_hash
        await self.bump_token_version(user)

    async def bump_token_version(self, user: User) -> None:
        """Atomic `token_version = token_version + 1` at the database, not a Python
        read-modify-write: two concurrent bumps (e.g. two password resets) must both
        land, never race to the same N+1 and silently un-revoke one of them."""
        await self._session.execute(
            update(User)
            .where(User.id == user.id)
            .values(token_version=User.token_version + 1)
        )
        await self._session.refresh(user, ["token_version"])

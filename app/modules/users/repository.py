"""Data-access layer for users.

The repository isolates all SQLAlchemy queries so the service layer can stay
focused on business rules and remain easy to unit-test against a fake.
"""
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User


class UserRepository:
    """CRUD operations for :class:`User`."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        # Compare case-insensitively so "User@x.com" and "user@x.com" collide.
        stmt = select(User).where(func.lower(User.email) == email.lower())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def exists_by_email(self, email: str) -> bool:
        stmt = select(User.id).where(func.lower(User.email) == email.lower())
        result = await self.session.execute(stmt)
        return result.first() is not None

    async def list(self, *, offset: int = 0, limit: int = 50) -> Sequence[User]:
        stmt = select(User).order_by(User.id).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(User))
        return int(result.scalar_one())

    def add(self, user: User) -> None:
        """Stage a new user; the caller commits."""
        self.session.add(user)

    async def delete(self, user: User) -> None:
        await self.session.delete(user)

    async def delete_unverified_before(self, cutoff: datetime) -> int:
        """Delete unverified accounts created before ``cutoff``.

        Returns the number of rows removed. Used by the periodic cleanup task.
        """
        stmt = delete(User).where(
            User.is_verified.is_(False),
            User.created_at < cutoff,
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0

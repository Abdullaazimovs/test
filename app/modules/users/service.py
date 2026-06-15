"""User management business logic (used by the ``/users`` and ``/me`` routes)."""
from app.core.exceptions import NotFoundError
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserUpdate


class UserService:
    """Operations on existing users that are not part of the auth flow."""

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def get(self, user_id: int) -> User:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    async def list(self, *, offset: int, limit: int) -> tuple[list[User], int]:
        users = list(await self.repository.list(offset=offset, limit=limit))
        total = await self.repository.count()
        return users, total

    async def update(self, user_id: int, payload: UserUpdate) -> User:
        """Apply a partial update.

        ``exclude_unset`` ensures only fields the client actually sent are
        touched, so PATCH never overwrites a field with its default.
        """
        user = await self.get(user_id)
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(user, field, value)
        await self.repository.session.commit()
        await self.repository.session.refresh(user)
        return user

    async def delete(self, user_id: int) -> None:
        user = await self.get(user_id)
        await self.repository.delete(user)
        await self.repository.session.commit()

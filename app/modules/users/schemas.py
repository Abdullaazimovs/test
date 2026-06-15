"""Pydantic schemas for the users module."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.users.models import UserRole


class UserBase(BaseModel):
    """Fields common to user representations."""

    email: EmailStr
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)


class UserRead(UserBase):
    """Public representation of a user returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    """Partial update payload (PATCH).

    Only the provided fields are applied. ``role`` and ``is_active`` are
    privileged fields enforced at the service/route layer (admins only).
    """

    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    role: UserRole | None = None
    is_active: bool | None = None


class UsersPage(BaseModel):
    """Paginated list of users."""

    items: list[UserRead]
    total: int
    offset: int
    limit: int

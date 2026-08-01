"""User ORM model and related enums."""
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class UserRole(StrEnum):
    """Authorization roles. ``ADMIN`` unlocks the user-management endpoints."""

    USER = "user"
    ADMIN = "admin"


class User(Base, TimestampMixin):
    """A registered user account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role"),
        default=UserRole.USER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Verification state. We keep the active code on the user row for
    # simplicity. In a larger system this belongs in a dedicated
    # ``verification_tokens`` table (one-to-many, with an audit trail and
    # support for both email and SMS channels simultaneously).
    verification_code: Mapped[str | None] = mapped_column(
        String(12), nullable=True
    )
    verification_code_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User id={self.id} email={self.email!r} role={self.role.value}>"

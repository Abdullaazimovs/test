"""Reusable FastAPI dependencies for authentication and authorization."""
from typing import Annotated

import jwt
from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import TokenType, decode_token
from app.modules.auth.service import AuthService
from app.modules.auth.verification import get_verification_sender
from app.modules.users.models import User, UserRole
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService

# ``auto_error=False`` lets us raise our own consistent ``AuthenticationError``
# instead of FastAPI's default 403 when the header is missing.
bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")

DbSession = Annotated[AsyncSession, Depends(get_db)]


# -- Repository / service providers -----------------------------------------
def get_user_repository(session: DbSession) -> UserRepository:
    return UserRepository(session)


UserRepo = Annotated[UserRepository, Depends(get_user_repository)]


def get_user_service(repository: UserRepo) -> UserService:
    return UserService(repository)


def get_auth_service(repository: UserRepo) -> AuthService:
    return AuthService(repository, get_verification_sender())


# -- Current user resolution -------------------------------------------------
async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(bearer_scheme)
    ],
    repository: UserRepo,
) -> User:
    """Resolve and return the user identified by a valid access token."""
    if credentials is None:
        raise AuthenticationError("Authentication credentials were not provided")

    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token has expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid authentication token") from exc

    if payload.get("type") != TokenType.ACCESS.value:
        raise AuthenticationError("Invalid token type")

    subject = payload.get("sub")
    if subject is None:
        raise AuthenticationError("Malformed token")

    user = await repository.get_by_id(int(subject))
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or disabled")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_verified_user(current_user: CurrentUser) -> User:
    """Require the caller to have completed verification."""
    if not current_user.is_verified:
        raise PermissionDeniedError("Email/phone verification is required")
    return current_user


def require_admin(current_user: CurrentUser) -> User:
    """Require the caller to hold the ``ADMIN`` role."""
    if current_user.role != UserRole.ADMIN:
        raise PermissionDeniedError("Administrator privileges are required")
    return current_user


AdminUser = Annotated[User, Depends(require_admin)]

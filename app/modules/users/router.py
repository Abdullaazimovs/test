"""User management HTTP endpoints (``/me`` and ``/users``)."""
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.core.exceptions import PermissionDeniedError
from app.modules.auth.dependencies import (
    AdminUser,
    CurrentUser,
    get_user_service,
)
from app.modules.users.models import UserRole
from app.modules.users.schemas import UserRead, UsersPage, UserUpdate
from app.modules.users.service import UserService

router = APIRouter(tags=["Users"])

UserServiceDep = Annotated[UserService, Depends(get_user_service)]


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get the current user",
    description="Return the profile of the authenticated user.",
)
async def read_me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.get(
    "/users",
    response_model=UsersPage,
    summary="List users (admin only)",
    description="Return a paginated list of all users. Requires the admin role.",
)
async def list_users(
    _admin: AdminUser,
    service: UserServiceDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> UsersPage:
    users, total = await service.list(offset=offset, limit=limit)
    return UsersPage(
        items=[UserRead.model_validate(u) for u in users],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/users/{user_id}",
    response_model=UserRead,
    summary="Get a user by ID (admin only)",
    description="Fetch a single user by their identifier. Requires the admin role.",
)
async def get_user(
    _admin: AdminUser,
    service: UserServiceDep,
    user_id: Annotated[int, Path(ge=1)],
) -> UserRead:
    user = await service.get(user_id)
    return UserRead.model_validate(user)


@router.patch(
    "/users/{user_id}",
    response_model=UserRead,
    summary="Partially update a user",
    description=(
        "Update a subset of a user's fields. A regular user may update only "
        "their own profile (name fields); changing `role` or `is_active`, or "
        "editing another user, requires the admin role."
    ),
)
async def update_user(
    current_user: CurrentUser,
    service: UserServiceDep,
    payload: UserUpdate,
    user_id: Annotated[int, Path(ge=1)],
) -> UserRead:
    is_admin = current_user.role == UserRole.ADMIN
    is_self = current_user.id == user_id

    if not is_admin and not is_self:
        raise PermissionDeniedError("You can only update your own profile")
    # Only admins may change privileged fields.
    if not is_admin and (payload.role is not None or payload.is_active is not None):
        raise PermissionDeniedError(
            "Only administrators can change role or active status"
        )

    user = await service.update(user_id, payload)
    return UserRead.model_validate(user)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user (admin only)",
    description="Permanently delete a user account. Requires the admin role.",
)
async def delete_user(
    _admin: AdminUser,
    service: UserServiceDep,
    user_id: Annotated[int, Path(ge=1)],
) -> None:
    await service.delete(user_id)

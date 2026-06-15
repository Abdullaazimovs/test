"""Pydantic schemas for the auth module."""
from pydantic import BaseModel, EmailStr, Field

from app.modules.users.schemas import UserRead


class SignupRequest(BaseModel):
    """Registration payload."""

    email: EmailStr
    # bcrypt only considers the first 72 bytes, so we cap the length here and
    # require a sensible minimum.
    password: str = Field(min_length=8, max_length=72)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    """Login payload (JSON). The OAuth2 password form is also supported."""

    email: EmailStr
    password: str


class TokenPair(BaseModel):
    """Access + refresh token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Refresh-token exchange payload."""

    refresh_token: str


class AccessToken(BaseModel):
    """Response for a refreshed access token."""

    access_token: str
    token_type: str = "bearer"


class VerifyRequest(BaseModel):
    """Email/SMS verification payload."""

    email: EmailStr
    code: str = Field(min_length=4, max_length=12)


class SignupResponse(BaseModel):
    """Returned after registration; the account is not yet verified."""

    user: UserRead
    message: str = (
        "Registration successful. A verification code has been sent "
        "(printed to the server console in dev mode)."
    )

"""Authentication & verification HTTP endpoints."""
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, status

from app.core.exceptions import AuthenticationError
from app.core.security import TokenType, decode_token
from app.modules.auth.dependencies import get_auth_service
from app.modules.auth.schemas import (
    AccessToken,
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    SignupResponse,
    TokenPair,
    VerifyRequest,
)
from app.modules.auth.service import AuthService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["Authentication"])

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description=(
        "Create a new account with email and password. The email must be "
        "unique. The account starts **unverified** and a verification code is "
        "generated and delivered (printed to the server console in dev mode)."
    ),
)
async def signup(payload: SignupRequest, service: AuthServiceDep) -> SignupResponse:
    user = await service.register(payload)
    return SignupResponse(user=UserRead.model_validate(user))


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Authenticate and obtain tokens",
    description=(
        "Verify email/password credentials and return a JWT access token "
        "(short-lived) together with a refresh token (long-lived)."
    ),
)
async def login(payload: LoginRequest, service: AuthServiceDep) -> TokenPair:
    return await service.login(payload.email, payload.password)


@router.post(
    "/refresh",
    response_model=AccessToken,
    summary="Refresh an access token",
    description=(
        "Exchange a valid refresh token for a new access token. The refresh "
        "token itself is not rotated here; rotation/blacklisting would be the "
        "next hardening step (see README)."
    ),
)
async def refresh(payload: RefreshRequest, service: AuthServiceDep) -> AccessToken:
    try:
        claims = decode_token(payload.refresh_token)
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Refresh token has expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid refresh token") from exc

    if claims.get("type") != TokenType.REFRESH.value:
        raise AuthenticationError("Provided token is not a refresh token")

    subject = claims.get("sub")
    if subject is None:
        raise AuthenticationError("Malformed refresh token")

    access_token = await service.refresh_access_token(int(subject))
    return AccessToken(access_token=access_token)


@router.post(
    "/verify",
    response_model=UserRead,
    summary="Verify an account",
    description=(
        "Confirm an account using the code delivered after signup. On success "
        "the account transitions to **verified**."
    ),
)
async def verify(payload: VerifyRequest, service: AuthServiceDep) -> UserRead:
    user = await service.verify(payload.email, payload.code)
    return UserRead.model_validate(user)

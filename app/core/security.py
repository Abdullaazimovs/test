"""Password hashing and JWT helpers.

We use ``bcrypt`` directly (instead of ``passlib``) to avoid the well-known
version-detection incompatibility between recent ``bcrypt`` releases and
``passlib`` and to keep the dependency surface small.
"""
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

# bcrypt only hashes the first 72 bytes of input; longer passwords are
# silently truncated. For a production system we would either enforce a max
# length at the schema layer or pre-hash with SHA-256. We enforce length in the
# registration schema (see app/modules/auth/schemas.py).
_BCRYPT_MAX_BYTES = 72


class TokenType(str, Enum):
    """Discriminates access tokens from refresh tokens via the ``type`` claim."""

    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(password: str) -> str:
    """Return a salted bcrypt hash for ``password``."""
    pwd_bytes = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Return ``True`` if ``password`` matches the stored ``hashed`` value."""
    pwd_bytes = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(pwd_bytes, hashed.encode("utf-8"))
    except ValueError:
        # Malformed hash in the database -> treat as a failed login.
        return False


def _create_token(
    subject: str | int,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Encode a signed JWT with standard ``sub``/``exp``/``iat``/``type`` claims."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_access_token(subject: str | int, **extra_claims: Any) -> str:
    """Create a short-lived access token."""
    return _create_token(
        subject,
        TokenType.ACCESS,
        timedelta(minutes=settings.access_token_expire_minutes),
        extra_claims or None,
    )


def create_refresh_token(subject: str | int) -> str:
    """Create a long-lived refresh token."""
    return _create_token(
        subject,
        TokenType.REFRESH,
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT, raising ``jwt.PyJWTError`` on any problem."""
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

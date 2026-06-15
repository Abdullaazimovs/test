"""Authentication, registration and verification business logic."""
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    ValidationError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.modules.auth.schemas import SignupRequest, TokenPair
from app.modules.auth.verification import (
    VerificationSender,
    generate_verification_code,
)
from app.modules.users.models import User
from app.modules.users.repository import UserRepository


class AuthService:
    """Coordinates the credential and verification lifecycle."""

    def __init__(
        self,
        repository: UserRepository,
        verification_sender: VerificationSender,
    ) -> None:
        self.repository = repository
        self.verification_sender = verification_sender

    # -- Registration -------------------------------------------------------
    async def register(self, payload: SignupRequest) -> User:
        """Create an unverified user and dispatch a verification code."""
        if await self.repository.exists_by_email(payload.email):
            raise ConflictError("A user with this email already exists")

        code = generate_verification_code()
        user = User(
            email=str(payload.email).lower(),
            hashed_password=hash_password(payload.password),
            first_name=payload.first_name,
            last_name=payload.last_name,
            is_verified=False,
            verification_code=code,
            verification_code_expires_at=self._code_expiry(),
        )
        self.repository.add(user)
        await self.repository.session.commit()
        await self.repository.session.refresh(user)

        await self.verification_sender.send(user.email, code)
        return user

    # -- Login --------------------------------------------------------------
    async def authenticate(self, email: str, password: str) -> User:
        """Validate credentials and return the user, or raise 401."""
        user = await self.repository.get_by_email(email)
        # Always run a hash comparison path; we still short-circuit on a
        # missing user. A constant-time dummy verify would further mitigate
        # user-enumeration timing attacks in a hardened build.
        if user is None or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Incorrect email or password")
        if not user.is_active:
            raise AuthenticationError("This account is disabled")
        return user

    async def login(self, email: str, password: str) -> TokenPair:
        user = await self.authenticate(email, password)
        return self._issue_tokens(user)

    # -- Refresh ------------------------------------------------------------
    async def refresh_access_token(self, user_id: int) -> str:
        """Issue a new access token for an already-validated refresh subject."""
        user = await self.repository.get_by_id(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("User no longer exists or is disabled")
        return create_access_token(user.id, role=user.role.value)

    # -- Verification -------------------------------------------------------
    async def verify(self, email: str, code: str) -> User:
        """Confirm a verification code and mark the account verified."""
        user = await self.repository.get_by_email(email)
        if user is None:
            raise ValidationError("Invalid verification request")
        if user.is_verified:
            raise ValidationError("Account is already verified")

        expires_at = user.verification_code_expires_at
        if (
            user.verification_code is None
            or expires_at is None
            or self._aware(expires_at) < datetime.now(UTC)
        ):
            raise ValidationError("Verification code has expired")
        if user.verification_code != code:
            raise ValidationError("Invalid verification code")

        user.is_verified = True
        user.verification_code = None
        user.verification_code_expires_at = None
        await self.repository.session.commit()
        await self.repository.session.refresh(user)
        return user

    # -- Helpers ------------------------------------------------------------
    def _issue_tokens(self, user: User) -> TokenPair:
        return TokenPair(
            access_token=create_access_token(user.id, role=user.role.value),
            refresh_token=create_refresh_token(user.id),
        )

    @staticmethod
    def _code_expiry() -> datetime:
        return datetime.now(UTC) + timedelta(
            minutes=settings.verification_code_ttl_minutes
        )

    @staticmethod
    def _aware(value: datetime) -> datetime:
        """Normalize a possibly-naive DB timestamp to UTC-aware.

        SQLite returns naive datetimes even for ``DateTime(timezone=True)``
        columns, so we attach UTC before comparing.
        """
        return value if value.tzinfo else value.replace(tzinfo=UTC)

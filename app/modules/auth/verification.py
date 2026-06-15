"""Verification code generation and delivery.

The delivery layer is abstracted behind :class:`VerificationSender` so the
transport (console / email / SMS) can be swapped without touching the auth
service. In ``dev`` we simply log the code to stdout, as allowed by the spec.

For a real deployment you would implement an ``EmailVerificationSender`` (e.g.
backed by SES/SendGrid) and an ``SmsVerificationSender`` (e.g. Twilio), select
one via configuration, and send asynchronously through Celery so the request
is not blocked on the third-party API.
"""
import logging
import secrets
from abc import ABC, abstractmethod

logger = logging.getLogger("users_api.verification")

_CODE_LENGTH = 6


def generate_verification_code() -> str:
    """Return a cryptographically-random numeric code (zero-padded)."""
    # secrets.randbelow gives a uniform integer in [0, 10**6); zfill keeps
    # leading zeros so the code is always 6 digits.
    return str(secrets.randbelow(10**_CODE_LENGTH)).zfill(_CODE_LENGTH)


class VerificationSender(ABC):
    """Strategy interface for delivering a verification code."""

    @abstractmethod
    async def send(self, recipient: str, code: str) -> None: ...


class ConsoleVerificationSender(VerificationSender):
    """Dev sender: prints the code to the application log/console."""

    async def send(self, recipient: str, code: str) -> None:
        logger.info(
            "[DEV] Verification code for %s is %s (do not use in production)",
            recipient,
            code,
        )
        # Also print so it is visible even without log configuration.
        print(f"[DEV] Verification code for {recipient}: {code}", flush=True)


def get_verification_sender() -> VerificationSender:
    """Return the configured sender.

    Currently always the console sender; wire real providers here based on
    ``settings.environment`` / a dedicated ``VERIFICATION_CHANNEL`` setting.
    """
    return ConsoleVerificationSender()

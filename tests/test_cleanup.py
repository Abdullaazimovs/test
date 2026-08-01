"""Tests for the automatic cleanup of stale, unverified accounts.

The Celery task itself is a thin wrapper (``asyncio.run`` + a short-lived
engine), so the tests target the repository query that carries the actual
deletion rule. That keeps them fast and free of a broker.
"""
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.core.security import hash_password
from app.modules.users.models import User, UserRole
from app.modules.users.repository import UserRepository


async def _add_user(
    session,
    email: str,
    *,
    created_at: datetime,
    is_verified: bool,
) -> None:
    """Insert a user with an explicit ``created_at`` to simulate its age."""
    session.add(
        User(
            email=email,
            hashed_password=hash_password("Password123"),
            role=UserRole.USER,
            is_active=True,
            is_verified=is_verified,
            created_at=created_at,
            updated_at=created_at,
        )
    )
    await session.commit()


async def test_purge_removes_only_stale_unverified_accounts(db_session):
    now = datetime.now(UTC)
    ttl = timedelta(hours=settings.unverified_account_ttl_hours)

    # Older than the 2-day TTL and still unverified -> must be removed.
    await _add_user(
        db_session, "stale@example.com", created_at=now - ttl - timedelta(hours=1),
        is_verified=False,
    )
    # Unverified but still inside the grace period -> must be kept.
    await _add_user(
        db_session, "fresh@example.com", created_at=now - timedelta(hours=1),
        is_verified=False,
    )
    # Old but verified -> must be kept.
    await _add_user(
        db_session, "verified@example.com", created_at=now - ttl - timedelta(days=5),
        is_verified=True,
    )

    repository = UserRepository(db_session)
    deleted = await repository.delete_unverified_before(now - ttl)
    await db_session.commit()

    assert deleted == 1
    assert await repository.get_by_email("stale@example.com") is None
    assert await repository.get_by_email("fresh@example.com") is not None
    assert await repository.get_by_email("verified@example.com") is not None


async def test_purge_is_a_noop_when_nothing_is_stale(db_session):
    now = datetime.now(UTC)
    ttl = timedelta(hours=settings.unverified_account_ttl_hours)

    await _add_user(
        db_session, "fresh@example.com", created_at=now, is_verified=False
    )

    repository = UserRepository(db_session)
    deleted = await repository.delete_unverified_before(now - ttl)
    await db_session.commit()

    assert deleted == 0
    assert await repository.count() == 1


def test_cleanup_task_is_registered_in_the_beat_schedule():
    """The purge task must actually be scheduled, not just defined."""
    from app.tasks.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule
    entry = schedule["purge-unverified-accounts"]
    assert entry["task"] == "app.tasks.cleanup.purge_unverified_accounts"

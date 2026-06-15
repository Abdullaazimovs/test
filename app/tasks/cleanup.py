"""Periodic cleanup of stale, unverified accounts."""
import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.modules.users.repository import UserRepository
from app.tasks.celery_app import celery_app

logger = logging.getLogger("users_api.cleanup")


async def _purge() -> int:
    """Delete unverified accounts older than the configured TTL.

    A short-lived engine is created per run so the coroutine owns its own
    asyncpg connection pool. This avoids sharing the FastAPI app's engine
    across the fresh event loop that Celery spins up for each task execution.
    """
    cutoff = datetime.now(UTC) - timedelta(
        hours=settings.unverified_account_ttl_hours
    )
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            deleted = await UserRepository(session).delete_unverified_before(cutoff)
            await session.commit()
            return deleted
    finally:
        await engine.dispose()


@celery_app.task(name="app.tasks.cleanup.purge_unverified_accounts")
def purge_unverified_accounts() -> int:
    """Celery entrypoint: bridge the sync worker to the async deletion logic."""
    deleted = asyncio.run(_purge())
    logger.info("Cleanup task removed %d unverified account(s)", deleted)
    return deleted

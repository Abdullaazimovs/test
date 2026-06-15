"""Startup helpers: schema creation (dev) and first-admin seeding."""
import logging

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password
from app.db.base import Base
from app.modules.users.models import User, UserRole
from app.modules.users.repository import UserRepository

logger = logging.getLogger("users_api.bootstrap")


async def create_schema() -> None:
    """Create tables from the ORM metadata.

    Convenience for local/dev runs (especially SQLite). In production Alembic
    migrations are the source of truth (see ``migrations/`` and the README);
    this is a no-op-safe fallback that only creates missing tables.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_first_admin() -> None:
    """Create the bootstrap admin from settings if it does not yet exist."""
    if not settings.first_admin_email or not settings.first_admin_password:
        return

    async with AsyncSessionLocal() as session:
        repository = UserRepository(session)
        if await repository.exists_by_email(settings.first_admin_email):
            return
        admin = User(
            email=settings.first_admin_email.lower(),
            hashed_password=hash_password(settings.first_admin_password),
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
        )
        repository.add(admin)
        await session.commit()
        logger.info("Seeded first admin account: %s", settings.first_admin_email)

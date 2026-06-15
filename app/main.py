"""FastAPI application factory and wiring."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.bootstrap import create_schema, seed_first_admin
from app.core.config import settings
from app.core.exceptions import AppError, app_error_handler
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Run startup tasks (schema + admin seed), then hand control to the app."""
    if settings.is_dev:
        # Production deployments run Alembic migrations instead (see README).
        await create_schema()
    await seed_first_admin()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.project_name,
        version="1.0.0",
        description=(
            "Users API — registration, JWT authentication, email/SMS "
            "verification and role-based user management. Built as a modular "
            "monolith with FastAPI and async SQLAlchemy."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Single handler for all expected domain errors -> consistent JSON output.
    app.add_exception_handler(AppError, app_error_handler)

    @app.get("/health", tags=["System"], summary="Health check")
    async def health() -> dict[str, str]:
        """Liveness probe for orchestrators and load balancers."""
        return {"status": "ok"}

    app.include_router(auth_router, prefix=settings.api_v1_prefix)
    app.include_router(users_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()

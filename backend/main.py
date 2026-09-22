from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.health import router as health_router
from api.v1.router import router as v1_router
from core.config import get_settings
from core.logging import configure_logging, request_id_middleware
from db.session import get_engine, get_session_factory
from dependencies.providers import get_auth_service, get_cache
from errors import register_exception_handlers

API_V1_PREFIX = "/api/v1"


async def _bootstrap_admin() -> None:
    """Creates the ADMIN_EMAIL account if it is missing (spec 4 §5.5). A missing
    `users` table fails startup loudly: run the migrations first."""
    settings = get_settings()
    async with get_session_factory()() as session:
        service = get_auth_service(session, settings)
        await service.ensure_admin(
            settings.admin_email, settings.admin_password.get_secret_value()
        )
        await session.commit()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await _bootstrap_admin()
    yield
    await get_cache().close()
    await get_engine().dispose()


def create_app() -> FastAPI:
    configure_logging(get_settings().log_level)
    app = FastAPI(title="Torobcar API", lifespan=lifespan)
    app.middleware("http")(request_id_middleware)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(v1_router, prefix=API_V1_PREFIX)
    return app


app = create_app()

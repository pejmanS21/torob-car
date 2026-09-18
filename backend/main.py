from fastapi import FastAPI

from api.health import router as health_router
from api.v1.router import router as v1_router
from core.config import get_settings
from core.logging import configure_logging, request_id_middleware
from errors import register_exception_handlers

API_V1_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    configure_logging(get_settings().log_level)
    app = FastAPI(title="Torobcar API")
    app.middleware("http")(request_id_middleware)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(v1_router, prefix=API_V1_PREFIX)
    return app


app = create_app()

"""
Main application entrypoint.

This module creates and infigures the FastAPI application,
including middleware, routers, and lifecycle events.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from prometheus_client import make_asgi_app

from app.core.config import settings
from app.core.logging import log
from app.lifecycle.app_lifecycle import AppLifecycle
from app.task.router import router as tasks_router
from app.user.router import admin_router
from app.user.router import router as users_router


def configure_cors(app: FastAPI) -> None:
    """
    Configure CORS middleware for the FastAPI application.

    Args:
        app: The FastAPI application instance.
    """
    if not settings.CORS_ORIGINS:
        return

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def setup_routers(app: FastAPI) -> None:
    """
    Include all API routers into the FastAPI application.

    Args:
        app: The FastAPI application instance.
    """
    app.include_router(admin_router)
    app.include_router(users_router)
    app.include_router(tasks_router)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager for startup and shutdown events.

    Args:
        app: The FastAPI application instance.

    Yields:
        None
    """
    lifecycle = AppLifecycle(app)
    await lifecycle.on_startup()
    try:
        yield
    finally:
        await lifecycle.on_shutdown()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        The configured FastAPI application instance.
    """
    log.info("Starting {} app", settings.APP_NAME)
    application = FastAPI(
        title=settings.APP_NAME,
        summary="Microservice to manage task",
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    configure_cors(application)
    setup_routers(application)

    # Mount the Prometheus metrics app
    application.mount("/metrics", make_asgi_app())

    # --- Add the root endpoint to redirect to docs ---
    @application.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        """Redirects the root path to the API documentation."""
        return RedirectResponse(url="/docs")

    return application


app = create_app()

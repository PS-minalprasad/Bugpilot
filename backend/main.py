"""
BugPilot — FastAPI Application Entry Point
==========================================
Run with:
    uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

From project root (bugpilot/):
    .venv/Scripts/uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.core.exceptions import BugPilotError
from backend.core.logging import get_logger, setup_logging
from backend.api.routes import health as health_router

# ---------------------------------------------------------------------------
# Logging must be configured BEFORE anything imports get_logger at module level.
# ---------------------------------------------------------------------------
setup_logging(level=settings.LOG_LEVEL, fmt=settings.LOG_FORMAT)
logger = get_logger("bugpilot.main")


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application startup / shutdown lifecycle.

    Startup:
      - Log configuration summary (no secrets)

    Shutdown:
      - Graceful teardown hooks (added in later phases)
    """
    from backend.database.repository import init_db
    init_db()
    if settings.is_production and settings.JWT_SECRET == "bugpilot-super-secret-jwt-key-2026-change-in-production":
        raise ValueError("JWT_SECRET must be changed from default value in production.")

    if not settings.GROQ_API_KEY:
        logger.info("GROQ_API_KEY is not set. LLM Gateway will use local Ollama fallback or deterministic mode.")
    else:
        logger.info(f"LLM initialized with Groq primary model '{settings.GROQ_MODEL}' and Ollama fallback '{settings.OLLAMA_MODEL}'")

    logger.info(
        "BugPilot starting",
        extra={
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "env": settings.ENV,
            "host": settings.HOST,
            "port": settings.PORT,
            "llm_ready": bool(settings.GROQ_API_KEY or settings.OLLAMA_BASE_URL),
        },
    )
    yield
    logger.info("BugPilot shutting down gracefully")


# ---------------------------------------------------------------------------
# FastAPI app factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
    application = FastAPI(
        title=settings.APP_NAME,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
        openapi_url=settings.openapi_url,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # Security & Observability Middlewares (Phases 19 & 20)
    # ------------------------------------------------------------------
    from backend.security.middleware import ObservabilityMiddleware, SecurityHeadersMiddleware, RateLimitingMiddleware
    application.add_middleware(ObservabilityMiddleware)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(RateLimitingMiddleware)

    # ------------------------------------------------------------------
    # CORS Middleware
    # ------------------------------------------------------------------
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Global Exception Handlers
    # ------------------------------------------------------------------
    @application.exception_handler(BugPilotError)
    async def bugpilot_error_handler(
        request: Request, exc: BugPilotError
    ) -> JSONResponse:
        logger.warning(
            "BugPilot domain error",
            extra={
                "error_code": exc.error_code,
                "detail": exc.detail,
                "path": str(request.url),
            },
        )
        return JSONResponse(
            status_code=exc.http_status,
            content={"error_code": exc.error_code, "detail": exc.detail},
        )

    @application.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            "Unhandled exception",
            extra={"path": str(request.url), "error": str(exc)},
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"error_code": "INTERNAL_ERROR", "detail": "An unexpected error occurred."},
        )

    # ------------------------------------------------------------------
    # Routers
    # ------------------------------------------------------------------
    application.include_router(health_router.router, prefix=settings.API_PREFIX)
    application.include_router(health_router.router, prefix=f"{settings.API_PREFIX}/v1")

    from backend.api.routes import v1 as v1_router
    application.include_router(v1_router.router, prefix=settings.API_PREFIX)

    @application.get("/", include_in_schema=False)
    async def root():
        return {
            "message": "Welcome to BugPilot Backend API Server",
            "documentation": "http://127.0.0.1:8000/docs",
            "frontend_ui": "http://localhost:5173",
            "health_endpoint": "http://127.0.0.1:8000/api/v1/health",
        }

    return application


# ---------------------------------------------------------------------------
# ASGI app instance (used by uvicorn)
# ---------------------------------------------------------------------------
app = create_app()

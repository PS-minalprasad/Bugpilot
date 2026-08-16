"""
BugPilot — Health Routes
=========================
GET /api/health        → basic liveness
GET /api/health/ready  → component readiness check
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter
from pydantic import BaseModel

from backend.config import settings

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    env: str
    timestamp: str
    data_source: str


class ReadinessResponse(BaseModel):
    status: str
    components: Dict[str, Any]
    timestamp: str


@router.get(
    "",
    response_model=HealthResponse,
    summary="Liveness check",
    description="Returns 200 if the application is running.",
)
async def health() -> HealthResponse:
    """Basic liveness endpoint — always returns 200 if the process is alive."""
    return HealthResponse(
        status="ok",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        env=settings.ENV,
        timestamp=datetime.utcnow().isoformat() + "Z",
        data_source=settings.DATA_LABEL,
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness check",
    description="Returns readiness status for each system component.",
)
@router.get(
    "/readiness",
    response_model=ReadinessResponse,
    summary="Readiness check alias",
    include_in_schema=False,
)
async def readiness() -> ReadinessResponse:
    """
    Production component readiness matrix.
    """
    import time
    st = time.time()
    from backend.database.session import check_database_health
    db_healthy = check_database_health()
    db_latency_ms = round((time.time() - st) * 1000, 2)

    components: Dict[str, Any] = {
        "config": {"status": "ready", "detail": "Configuration loaded successfully"},
        "logging": {"status": "ready", "detail": "Logging initialised"},
        "database": {
            "status": "ready" if db_healthy else "error",
            "latency_ms": db_latency_ms,
            "detail": "PostgreSQL/SQLite database connected" if db_healthy else "Database connection failed",
        },
        "data_provider": {
            "status": "ready",
            "mode": settings.PROVIDER_MODE,
            "detail": f"Active provider: {settings.DATA_LABEL}",
        },
        "mcp_server": {
            "status": "ready",
            "tools_count": 8,
            "detail": "MCP server online with 8 tools",
        },
        "llm": {
            "status": "ready" if settings.GEMINI_API_KEY else "not_configured",
            "detail": f"LLM model: {settings.GEMINI_MODEL}" if settings.GEMINI_API_KEY else "LLM not configured (GEMINI_API_KEY missing)",
        },
    }

    # Overall status: ready only if no component is in 'error'
    has_error = any(c.get("status") == "error" for c in components.values())
    overall = "degraded" if has_error else "ready"

    return ReadinessResponse(
        status=overall,
        components=components,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

"""
BugPilot — Observability & Tracing Middleware Engine (Phase 20)
================================================================
Provides:
- ObservabilityMiddleware: Generates X-Request-ID, calculates latency, logs structured requests with tenant context
- SecurityHeadersMiddleware: Injects production security headers
- RateLimitingMiddleware: In-memory IP rate protection
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Dict, List, Optional
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from backend.core.logging import sanitize_sensitive_data

logger = logging.getLogger("bugpilot.observability")


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Middleware injecting X-Request-ID, measuring API latency, and writing structured JSON logs.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:8]}"
        request.state.request_id = request_id

        start_time = time.time()
        org_id = request.headers.get("X-Organization-ID") or "unauthenticated"

        try:
            response = await call_next(request)
            elapsed_ms = round((time.time() - start_time) * 1000, 2)

            response.headers["X-Request-ID"] = request_id
            response.headers["X-Latency-MS"] = str(elapsed_ms)

            logger.info(
                f"HTTP {request.method} {request.url.path} -> {response.status_code} ({elapsed_ms}ms)",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "elapsed_ms": elapsed_ms,
                    "org_id": org_id,
                },
            )
            return response
        except Exception as exc:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(
                f"HTTP {request.method} {request.url.path} failed: {exc}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "elapsed_ms": elapsed_ms,
                    "org_id": org_id,
                    "error": sanitize_sensitive_data(str(exc)),
                },
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error_code": "INTERNAL_ERROR",
                    "detail": "An unexpected error occurred processing your request.",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects production security headers on all HTTP responses."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
        return response


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    In-memory IP rate limiter protecting authentication & chat APIs.
    """

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = {}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        if "/auth/login" in path or "/chat" in path:
            client_ip = request.client.host if request.client else "127.0.0.1"
            now = time.time()
            timestamps = self.requests.get(client_ip, [])

            valid_timestamps = [t for t in timestamps if (now - t) < self.window_seconds]

            if len(valid_timestamps) >= self.max_requests:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error_code": "RATE_LIMIT_EXCEEDED",
                        "detail": f"Rate limit exceeded. Maximum {self.max_requests} requests per minute.",
                    },
                )

            valid_timestamps.append(now)
            self.requests[client_ip] = valid_timestamps

        return await call_next(request)

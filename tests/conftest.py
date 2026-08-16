"""
BugPilot — pytest conftest.py
==============================
Shared fixtures available to all tests.

Fixtures defined here are automatically discovered by pytest
without explicit imports in test files.
"""

from __future__ import annotations

import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Force ENV=test so config validators pass and DEBUG is predictable.
# ---------------------------------------------------------------------------
os.environ.setdefault("ENV", "test")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("LOG_LEVEL", "DEBUG")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def app():
    """Return the FastAPI application instance (session-scoped)."""
    from backend.main import app as _app
    return _app


@pytest.fixture
async def client(app):
    """
    Async HTTPX test client wrapping the FastAPI app.

    Uses ASGITransport so no network socket is opened.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

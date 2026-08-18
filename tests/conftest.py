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


@pytest.fixture(autouse=True)
def mock_llm_for_tests(request, monkeypatch):
    """
    Mock generate_react_decision in tests so integration and unit tests
    do not call live Groq/Ollama APIs or fail on quota / missing keys.
    Live tests decorated with @pytest.mark.llm are bypassed.
    """
    if "llm" in request.keywords:
        return

    async def _mock_generate_react_decision(goal: str, tools_text: str, state: dict):
        obs = state.get("observations", {})
        q = goal.lower()

        # Multi-step handling for multi-step tests
        if ("metric" in q or "count" in q or "overview" in q) and "component" in q and "trend" in q:
            if "get_bug_metrics" not in obs:
                return {"action": "CALL_TOOL", "tool_name": "get_bug_metrics", "arguments": {}}
            elif "get_component_risk" not in obs:
                return {"action": "CALL_TOOL", "tool_name": "get_component_risk", "arguments": {}}
            elif "get_bug_trends" not in obs:
                return {"action": "CALL_TOOL", "tool_name": "get_bug_trends", "arguments": {}}
            else:
                return {"action": "FINISH"}

        if "report" in q or "executive" in q or "health" in q or "leadership" in q or "system report" in q:
            if "get_bug_metrics" not in obs:
                return {"action": "CALL_TOOL", "tool_name": "get_bug_metrics", "arguments": {}}
            elif "get_component_risk" not in obs:
                return {"action": "CALL_TOOL", "tool_name": "get_component_risk", "arguments": {}}
            else:
                return {"action": "FINISH"}

        if "component" in q and ("how many" in q or "open bugs" in q):
            if "get_component_risk" not in obs:
                return {"action": "CALL_TOOL", "tool_name": "get_component_risk", "arguments": {}}
            elif "get_bug_metrics" not in obs:
                return {"action": "CALL_TOOL", "tool_name": "get_bug_metrics", "arguments": {}}
            else:
                return {"action": "FINISH"}

        # If we already have observations, finish unless multi-step
        if obs:
            return {"action": "FINISH"}

        def _pick(tool_name, default_args=None):
            if tools_text and tool_name not in tools_text:
                return None
            return {"action": "CALL_TOOL", "tool_name": tool_name, "arguments": default_args or {}}

        # Heuristic mapping for single/first step
        if ("reopened" in q or "reopen" in q or "churn" in q) and _pick("get_reopened_bugs"):
            return _pick("get_reopened_bugs")

        if ("aging" in q or "stagnant" in q or "older than" in q or "backlog" in q or "old" in q) and _pick("get_aging_bugs"):
            return _pick("get_aging_bugs")

        if ("increasing" in q or "decreasing" in q or "trend" in q or "velocity" in q) and _pick("get_bug_trends"):
            return _pick("get_bug_trends")

        if ("release" in q or "deploy" in q or "safe" in q or "readiness" in q or "production" in q) and _pick("get_release_risk"):
            return _pick("get_release_risk")

        if ("component" in q or "danger" in q or "riskiest" in q or "risk" in q) and _pick("get_component_risk"):
            return _pick("get_component_risk")

        import re
        bug_match = re.search(r"(live-[a-zA-Z0-9_-]+|bp-[a-zA-Z0-9_-]+|iss-[a-zA-Z0-9_-]+|[a-zA-Z]+-\d+)", q)
        if bug_match and _pick("get_bug"):
            bug_id = bug_match.group(1).upper()
            return {"action": "CALL_TOOL", "tool_name": "get_bug", "arguments": {"bug_id": bug_id}}

        if "nonexistentbug" in q and _pick("get_bug"):
            return {"action": "CALL_TOOL", "tool_name": "get_bug", "arguments": {"bug_id": "NonExistentBugXyz999"}}

        if ("search" in q or "find" in q or "list" in q or "login" in q or "auth" in q or "billing" in q or "token" in q or "about the" in q or "payment" in q or "unresolved" in q) and _pick("search_bugs"):
            from agents.orchestrator import OrchestratorAgent
            search_term = OrchestratorAgent._extract_search_query(goal)
            return {"action": "CALL_TOOL", "tool_name": "search_bugs", "arguments": {"query": search_term}}

        if _pick("get_bug_metrics"):
            return _pick("get_bug_metrics")
        elif _pick("get_bug"):
            return _pick("get_bug", {"bug_id": "BP-101"})
        elif _pick("search_bugs"):
            return _pick("search_bugs", {"query": "bug"})

        return {"action": "FINISH"}

    monkeypatch.setattr("agents.orchestrator.generate_react_decision", _mock_generate_react_decision)

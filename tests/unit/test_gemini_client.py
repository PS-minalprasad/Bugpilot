"""
BugPilot — Gemini LLM Integration Tests
=======================================
Tests for:
- Graceful deterministic fallback when API key is missing or invalid
- Real Gemini API grounded analysis generation (@pytest.mark.llm, skipped by default)
"""

import os
import pytest
from unittest.mock import patch

from backend.config import settings
from backend.llm.gemini_client import generate_analysis


@pytest.mark.asyncio
async def test_gemini_client_missing_key_fallback():
    """Verify generate_analysis returns None when GEMINI_API_KEY is empty."""
    with patch.object(settings, "GEMINI_API_KEY", ""):
        res = await generate_analysis(
            evidence={"bug_id": "BP-101", "status": "Open", "component": "Auth"},
            question="Analyze root cause of BP-101",
        )
        assert res is None


@pytest.mark.asyncio
async def test_gemini_client_network_error_fallback():
    """Verify generate_analysis returns None on network/API failure without raising."""
    with patch.object(settings, "GEMINI_API_KEY", "invalid_dummy_key_12345"):
        res = await generate_analysis(
            evidence={"bug_id": "BP-101", "status": "Open"},
            question="What is the root cause?",
        )
        assert res is None


@pytest.mark.llm
@pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not configured in environment; skipping live LLM test.",
)
@pytest.mark.asyncio
async def test_gemini_client_real_api_grounded_analysis():
    """Live test against Google Gemini API ensuring evidence-grounded response."""
    evidence = {
        "bug_id": "BP-800",
        "title": "OAuth Token Expired Exception",
        "component": "Authentication",
        "status": "Open",
        "severity": "Critical",
        "priority": "High",
        "description": "JWT tokens fail refresh when Redis cache is unreachable.",
    }
    question = "Analyze BP-800 based strictly on the provided evidence."
    res = await generate_analysis(evidence=evidence, question=question)

    assert res is not None
    assert isinstance(res, str)
    assert len(res) > 10
    # Must reference evidence details
    assert "Authentication" in res or "BP-800" in res or "token" in res.lower() or "redis" in res.lower()


@pytest.mark.llm
@pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not configured in environment; skipping live LLM test.",
)
@pytest.mark.asyncio
async def test_gemini_client_real_api_insufficient_evidence():
    """Live test ensuring Gemini states lack of evidence when root cause is omitted."""
    evidence = {
        "bug_id": "BP-900",
        "title": "Intermittent 500 error on checkout",
        "component": "Payments",
        "status": "Open",
        "severity": "High",
        "priority": "High",
        "description": "User reported checkout failure once on Friday.",
    }
    question = "What is the confirmed database deadlock root cause?"
    res = await generate_analysis(evidence=evidence, question=question)

    assert res is not None
    assert isinstance(res, str)
    # The prompt instructs model never to invent root causes not in evidence
    res_lower = res.lower()
    assert any(phrase in res_lower for phrase in ["evidence", "not provided", "available data", "insufficient", "not enough", "cannot", "does not contain", "no information", "not mentioned", "not stated"])

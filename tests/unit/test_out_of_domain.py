"""
Unit tests verifying out-of-domain query handling in BugPilot.
Out-of-domain queries should NOT invoke MCP tools or specialist agents,
and should return an early boundary response.
"""

import pytest
from mcp_client import MCPClient
from agents.orchestrator import OrchestratorAgent
from backend.api.routes.v1 import ChatRequest, post_chat_v1
from backend.security.auth import User


@pytest.mark.asyncio
async def test_out_of_domain_queries_direct():
    """Verify out-of-domain queries return early domain message with 0 steps."""
    out_of_domain_samples = [
        "Tell me about prime numbers",
        "What is the capital of France?",
        "Write a poem about sunflowers",
        "Who is Isaac Newton?",
        "How do I make chocolate chip cookies?",
        "What is the distance to the moon?",
    ]

    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        for q in out_of_domain_samples:
            res = await orchestrator.run(q)
            assert res.intent == "OUT_OF_DOMAIN", f"Expected OUT_OF_DOMAIN for '{q}', got '{res.intent}'"
            assert res.total_steps == 0, f"Expected 0 steps for '{q}', got {res.total_steps}"
            assert len(res.execution_steps) == 0
            assert "I can only help with BugPilot bug, risk, trend, and project analysis" in res.final_answer


@pytest.mark.asyncio
async def test_in_domain_queries_still_execute():
    """Verify in-domain queries are not falsely rejected."""
    in_domain_samples = [
        "Tell me about Payments Bugs",
        "What is the status of BP-999?",
        "Show me critical unresolved bugs",
        "How many open bugs in Authentication?",
        "Are bugs increasing this sprint?",
        "What is the riskiest component?",
        "Is it safe to deploy?",
    ]

    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        for q in in_domain_samples:
            assert not orchestrator._is_out_of_domain(q), f"'{q}' should be IN_DOMAIN"
            classified = orchestrator._classify_intent(q)
            assert classified["intent"] != "OUT_OF_DOMAIN"


@pytest.mark.asyncio
async def test_out_of_domain_chat_endpoint():
    """Verify POST /api/v1/chat returns clean response without agent or tool execution."""
    user = User(
        id="usr-test-1",
        email="test@acme.com",
        username="testuser",
        full_name="Test User",
        org_id="org-acme",
        role="Developer",
    )
    req = ChatRequest(message="Tell me about prime numbers")
    res = await post_chat_v1(req, current_user=user)

    assert res.intent == "OUT_OF_DOMAIN"
    assert "I can only help with BugPilot bug, risk, trend, and project analysis" in res.answer
    assert res.agents_used == []
    assert res.tools_used == []
    assert res.reflection["verdict"] == "CONFIRM"

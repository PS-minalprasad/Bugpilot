import pytest
from mcp_client.client import MCPClient
from agents.orchestrator import OrchestratorAgent


@pytest.mark.asyncio
async def test_comparative_query_intent_classification():
    """Test that comparative and highest-risk bug queries are correctly classified."""
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)

        c1 = orchestrator._classify_intent("analyze authentication bugs and identify the highest-risk issue")
        assert c1["intent"] == "COMPARATIVE_RISK"
        assert c1["tool"] == "search_bugs"
        assert "auth" in c1["arguments"].get("query", "").lower()

        c2 = orchestrator._classify_intent("compare payment bugs and find the most critical one")
        assert c2["intent"] == "COMPARATIVE_RISK"
        assert c2["tool"] == "search_bugs"

        c3 = orchestrator._classify_intent("which open bug in billing has the highest risk?")
        assert c3["intent"] == "COMPARATIVE_RISK"
        assert c3["tool"] == "search_bugs"


def test_risk_scoring_differentiation_no_100_saturation_or_ties():
    """Test that risk scoring accurately differentiates defects without 100/100 saturation or ties."""
    bug_security = {
        "id": "BP-133",
        "title": "Authentication session fixation on customer portal login",
        "severity": "Critical",
        "priority": "High",
        "status": "Open",
        "environment": "production",
        "business_impact": "Security compliance vulnerability in SOC2 audit; potential session hijacking risk.",
        "root_cause": "JWT refresh token rotation does not invalidate existing session cookie.",
    }

    bug_passkey_crash = {
        "id": "BP-132",
        "title": "Login page crash on biometric Passkey authentication",
        "severity": "Critical",
        "priority": "High",
        "status": "Open",
        "environment": "production",
        "business_impact": "Prevents 100% of Passkey / FaceID users on iOS 17 and macOS Sonoma from logging in.",
        "root_cause": "WebAuthn client credential parser assumes non-null authenticatorData buffer.",
    }

    bug_sso_loop = {
        "id": "BP-101",
        "title": "Authentication token expiry causes UI loop",
        "severity": "Critical",
        "priority": "High",
        "status": "Open",
        "environment": "production",
        "business_impact": "Degraded user login success rate by ~4.2% during peak morning authentication traffic.",
        "root_cause": "Race condition in OAuth token exchange handler under concurrent requests.",
    }

    bug_edge_skew = {
        "id": "BP-999",
        "title": "Authentication token validation error on distributed edge cache",
        "severity": "Critical",
        "priority": "High",
        "status": "Open",
        "environment": "production",
        "business_impact": "Intermittent 401 Unauthorized errors for ~2.3% of global users on edge proxy endpoints.",
        "root_cause": "JWT 'nbf' (not before) assertion tolerance set to 0 seconds instead of 60s leeway.",
    }

    score_sec, tier_sec = OrchestratorAgent._calculate_bug_risk_score(bug_security)
    score_passkey, tier_passkey = OrchestratorAgent._calculate_bug_risk_score(bug_passkey_crash)
    score_sso, tier_sso = OrchestratorAgent._calculate_bug_risk_score(bug_sso_loop)
    score_edge, tier_edge = OrchestratorAgent._calculate_bug_risk_score(bug_edge_skew)

    # Assert no 100.0 saturation
    assert score_sec < 100.0
    assert score_passkey < 100.0
    assert score_sso < 100.0
    assert score_edge < 100.0

    # Assert strict differentiation (no ties between distinct evidence)
    assert score_sec > score_passkey, f"Expected BP-133 ({score_sec}) > BP-132 ({score_passkey})"
    assert score_passkey > score_sso, f"Expected BP-132 ({score_passkey}) > BP-101 ({score_sso})"
    assert score_sso > score_edge, f"Expected BP-101 ({score_sso}) > BP-999 ({score_edge})"

    assert tier_sec == "Critical"
    assert tier_passkey == "Critical"
    assert tier_sso == "Critical"


@pytest.mark.asyncio
async def test_comparative_fallback_synthesis_inspected_vs_uninspected():
    """Test deterministic comparative synthesis strictly evaluates inspected bugs and separates uninspected candidates."""
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)

        sample_observations = {
            "search_bugs": {
                "bugs": [
                    {
                        "id": "BP-101",
                        "title": "OAuth token expiration causes authentication loop",
                        "component": "Authentication",
                        "severity": "critical",
                        "priority": "high",
                        "status": "open",
                    },
                    {
                        "id": "BP-133",
                        "title": "Session token reuse vulnerability in OAuth refresh flow",
                        "component": "Authentication",
                        "severity": "critical",
                        "priority": "high",
                        "status": "open",
                    },
                    {
                        "id": "BP-132",
                        "title": "Password reset email template broken HTML",
                        "component": "Authentication",
                        "severity": "medium",
                        "priority": "low",
                        "status": "open",
                    },
                ]
            },
            # Only BP-101 and BP-133 were inspected via get_bug; BP-132 was not
            "get_bug_BP-101": {
                "found": True,
                "bug": {
                    "id": "BP-101",
                    "title": "OAuth token expiration causes authentication loop",
                    "component": "Authentication",
                    "severity": "Critical",
                    "priority": "High",
                    "status": "Open",
                    "environment": "production",
                    "root_cause": "Race condition in refresh token rotation logic in AuthGateway.",
                    "business_impact": "Degraded user login success rate by ~4.2% during peak morning authentication traffic.",
                    "description": "Users report endless redirect loops during token refresh.",
                },
            },
            "get_bug_BP-133": {
                "found": True,
                "bug": {
                    "id": "BP-133",
                    "title": "Session token reuse vulnerability in OAuth refresh flow",
                    "component": "Authentication",
                    "severity": "Critical",
                    "priority": "High",
                    "status": "Open",
                    "environment": "production",
                    "root_cause": "JWT refresh token rotation does not invalidate existing session cookie.",
                    "business_impact": "Security compliance vulnerability in SOC2 audit; potential session hijacking risk.",
                    "description": "Customer portal session ID remains unchanged after privilege upgrade.",
                },
            },
        }

        report = orchestrator._synthesize_fallback_answer(
            query="analyze authentication bugs and identify the highest-risk issue",
            observations=sample_observations,
        )

        # Verify Markdown structure
        assert "# Comparative Bug & Risk Analysis Report" in report
        assert "## 1. Executive Summary" in report
        assert "## 2. Comparative Bug Evaluation Matrix" in report
        assert "## 3. Highest-Risk Issue Determination & Rationale" in report
        assert "## 4. Problem & Impact Analysis of Evaluated Issues" in report
        assert "## 5. Risk Assessment & Remediation Priority" in report
        assert "## 6. Recommended Actions" in report
        assert "## 7. Additional Discovered Candidates (Uninspected)" in report

        # Evaluated matrix contains BP-133 and BP-101
        assert "BP-133" in report
        assert "BP-101" in report
        assert "BP-133" in report.split("## 3. Highest-Risk Issue Determination")[1]

        # Uninspected section mentions BP-132 without evaluating root cause
        assert "BP-132" in report.split("## 7. Additional Discovered Candidates (Uninspected)")[1]


@pytest.mark.asyncio
async def test_comparative_react_inspects_each_candidate_before_finish():
    """Test full ReAct loop executes search_bugs then iteratively inspects candidates with get_bug."""
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        result = await orchestrator.run("analyze authentication bugs and identify the highest-risk issue")

        assert result.intent in ["COMPARATIVE_RISK", "RISK", "BUG_SEARCH", "SPECIFIC_BUG", "REPORT"]
        assert len(result.execution_steps) >= 2

        # Verify tool calls executed
        tools_called = [s.tool_name for s in result.execution_steps if s.tool_name]
        assert "search_bugs" in tools_called
        assert "get_bug" in tools_called

        # Verify final report
        assert result.final_answer is not None
        assert len(result.final_answer.strip()) > 100
        assert "highest-risk" in result.final_answer.lower() or "highest risk" in result.final_answer.lower() or "risk" in result.final_answer.lower()


@pytest.mark.asyncio
async def test_comparative_react_4_candidates_4_get_bug_calls_to_finish():
    """
    Test explicitly that when search_bugs returns 4 candidates:
    4 candidates -> 4 get_bug calls -> comparison matrix -> FINISH.
    """
    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)

        # Mock LLM to always propose FINISH, verifying orchestrator intercepts until all 4 candidates are inspected
        async def mock_llm_finish(*args, **kwargs):
            return {"action": "FINISH", "final_answer": "Premature finish attempt."}

        orchestrator._ask_llm_for_next_action = mock_llm_finish

        result = await orchestrator.run("compare all authentication bugs and find highest-risk")

        # 1 search_bugs + 4 get_bug calls = 5 tool execution steps
        get_bug_steps = [s for s in result.execution_steps if s.tool_name == "get_bug"]
        assert len(get_bug_steps) == 4, f"Expected exactly 4 get_bug calls for 4 candidates, got {len(get_bug_steps)}"

        # Verify inspected candidate IDs
        inspected_ids = set()
        for s in result.execution_steps:
            if s.tool_name == "get_bug":
                # Check summary or observations
                inspected_ids.add(s.result_summary)

        assert result.status == "success"
        assert "# Comparative Bug & Risk Analysis Report" in result.final_answer
        assert "## 2. Comparative Bug Evaluation Matrix" in result.final_answer
        assert "BP-101" in result.final_answer
        assert "BP-132" in result.final_answer
        assert "BP-133" in result.final_answer
        assert "BP-999" in result.final_answer

"""
BugPilot — LLM Gateway, Providers & ReAct Validation Unit Tests
================================================================
Tests Groq (primary), Ollama (fallback), LLMGateway automatic failover, and strict ReAct JSON validation.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.config import settings
from backend.llm.base import BaseLLMProvider
from backend.llm.gateway import (
    LLMGateway,
    generate_analysis,
    generate_react_decision,
    parse_react_decision,
)
from backend.llm.providers.groq import GroqProvider
from backend.llm.providers.ollama import OllamaProvider
from backend.llm.schemas import ReActAction, ReActDecision


# ============================================================================
# 1. REACT JSON PARSING & VALIDATION TESTS
# ============================================================================


def test_parse_react_decision_clean_json_call_tool():
    """Verify parsing a clean CALL_TOOL JSON."""
    raw = json.dumps({
        "action": "CALL_TOOL",
        "tool_name": "get_bug_metrics",
        "arguments": {"project": "BugPilot"},
    })
    decision = parse_react_decision(raw)
    assert decision["action"] == "CALL_TOOL"
    assert decision["tool_name"] == "get_bug_metrics"
    assert decision["arguments"] == {"project": "BugPilot"}


def test_parse_react_decision_clean_json_delegate():
    """Verify parsing a clean DELEGATE JSON."""
    raw = json.dumps({
        "action": "DELEGATE",
        "agent": "Risk Analyst",
        "task": "Evaluate component risk scores",
    })
    decision = parse_react_decision(raw)
    assert decision["action"] == "DELEGATE"
    assert decision["agent"] == "Risk Analyst"
    assert decision["task"] == "Evaluate component risk scores"


def test_parse_react_decision_clean_json_finish():
    """Verify parsing a clean FINISH JSON."""
    raw = json.dumps({
        "action": "FINISH",
        "final_answer": "Analysis is complete with 10 total bugs.",
    })
    decision = parse_react_decision(raw)
    assert decision["action"] == "FINISH"
    assert decision["final_answer"] == "Analysis is complete with 10 total bugs."


def test_parse_react_decision_markdown_fenced():
    """Verify parser extracts JSON from markdown code fences."""
    raw = "```json\n{\n  \"action\": \"CALL_TOOL\",\n  \"tool_name\": \"get_bug_trends\",\n  \"arguments\": {}\n}\n```"
    decision = parse_react_decision(raw)
    assert decision["action"] == "CALL_TOOL"
    assert decision["tool_name"] == "get_bug_trends"


def test_parse_react_decision_surrounding_text():
    """Verify parser extracts JSON surrounded by text."""
    raw = "Here is my ReAct decision:\n{\"action\": \"FINISH\"}\nHope this helps."
    decision = parse_react_decision(raw)
    assert decision["action"] == "FINISH"


def test_parse_react_decision_invalid_action():
    """Verify parser rejects unknown actions."""
    raw = json.dumps({"action": "EXECUTE_ARBITRARY_CODE", "tool": "rm"})
    with pytest.raises(ValueError):
        parse_react_decision(raw)


def test_parse_react_decision_empty():
    """Verify parser rejects empty input."""
    with pytest.raises(ValueError):
        parse_react_decision("")


# ============================================================================
# 2. GROQ PROVIDER UNIT TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_groq_provider_react_decision_success():
    """Verify GroqProvider generates validated ReActDecision on 200 response."""
    provider = GroqProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"action": "CALL_TOOL", "tool_name": "get_bug", "arguments": {"bug_id": "BP-101"}}'
                }
            }
        ]
    }

    with patch.object(settings, "GROQ_API_KEY", "gsk_test_key"), \
         patch("httpx.AsyncClient.post", return_value=mock_resp):
        decision = await provider.generate_react_decision(
            goal="Inspect bug BP-101",
            tools_text="[]",
            available_agents=[],
            state={},
        )
        assert decision is not None
        assert decision.action == ReActAction.CALL_TOOL
        assert decision.tool_name == "get_bug"
        assert decision.arguments == {"bug_id": "BP-101"}


@pytest.mark.asyncio
async def test_groq_provider_analysis_success():
    """Verify GroqProvider generates analysis text."""
    provider = GroqProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "Evidence-grounded report from Groq."
                }
            }
        ]
    }

    with patch.object(settings, "GROQ_API_KEY", "gsk_test_key"), \
         patch("httpx.AsyncClient.post", return_value=mock_resp):
        analysis = await provider.generate_analysis(
            evidence={"total_bugs": 5},
            question="Summarize bugs",
        )
        assert analysis == "Evidence-grounded report from Groq."


# ============================================================================
# 3. OLLAMA PROVIDER UNIT TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_ollama_provider_react_decision_success():
    """Verify OllamaProvider generates validated ReActDecision on 200 response."""
    provider = OllamaProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "message": {
            "content": '{"action": "DELEGATE", "agent": "Bug Analyst", "task": "Check authentication bugs"}'
        }
    }

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        decision = await provider.generate_react_decision(
            goal="Analyze auth bugs",
            tools_text="[]",
            available_agents=[],
            state={},
        )
        assert decision is not None
        assert decision.action == ReActAction.DELEGATE
        assert decision.agent == "Bug Analyst"


@pytest.mark.asyncio
async def test_ollama_provider_analysis_success():
    """Verify OllamaProvider generates analysis text."""
    provider = OllamaProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "message": {
            "content": "Evidence-grounded report from Ollama fallback."
        }
    }

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        analysis = await provider.generate_analysis(
            evidence={"total_bugs": 5},
            question="Summarize bugs",
        )
        assert analysis == "Evidence-grounded report from Ollama fallback."


# ============================================================================
# 4. LLM GATEWAY AUTOMATIC FALLBACK TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_gateway_groq_429_falls_back_to_ollama():
    """Verify Groq HTTP 429 automatically triggers fallback to Ollama."""
    groq_mock = AsyncMock(spec=BaseLLMProvider)
    groq_mock.provider_name = "groq"
    groq_mock.generate_react_decision.side_effect = RuntimeError("Groq API error HTTP 429: Rate limit exceeded")

    ollama_mock = AsyncMock(spec=BaseLLMProvider)
    ollama_mock.provider_name = "ollama"
    ollama_mock.generate_react_decision.return_value = ReActDecision(
        action=ReActAction.CALL_TOOL,
        tool_name="get_component_risk",
        arguments={},
    )

    gateway = LLMGateway(primary_provider=groq_mock, fallback_provider=ollama_mock)
    decision = await gateway.generate_react_decision(
        goal="Check risk",
        tools_text="[]",
        state={},
    )

    assert decision is not None
    assert decision["action"] == "CALL_TOOL"
    assert decision["tool_name"] == "get_component_risk"
    groq_mock.generate_react_decision.assert_awaited_once()
    ollama_mock.generate_react_decision.assert_awaited_once()


@pytest.mark.asyncio
async def test_gateway_groq_timeout_falls_back_to_ollama():
    """Verify Groq timeout automatically triggers fallback to Ollama."""
    groq_mock = AsyncMock(spec=BaseLLMProvider)
    groq_mock.provider_name = "groq"
    groq_mock.generate_react_decision.side_effect = TimeoutError("Groq timed out")

    ollama_mock = AsyncMock(spec=BaseLLMProvider)
    ollama_mock.provider_name = "ollama"
    ollama_mock.generate_react_decision.return_value = ReActDecision(
        action=ReActAction.FINISH,
        final_answer="Analysis complete via Ollama.",
    )

    gateway = LLMGateway(primary_provider=groq_mock, fallback_provider=ollama_mock)
    decision = await gateway.generate_react_decision(
        goal="Check trends",
        tools_text="[]",
        state={},
    )

    assert decision is not None
    assert decision["action"] == "FINISH"
    assert decision["final_answer"] == "Analysis complete via Ollama."


@pytest.mark.asyncio
async def test_gateway_both_providers_fail_raises():
    """Verify error is raised when both primary and fallback providers fail."""
    groq_mock = AsyncMock(spec=BaseLLMProvider)
    groq_mock.provider_name = "groq"
    groq_mock.generate_react_decision.side_effect = RuntimeError("Groq down")

    ollama_mock = AsyncMock(spec=BaseLLMProvider)
    ollama_mock.provider_name = "ollama"
    ollama_mock.generate_react_decision.side_effect = RuntimeError("Ollama down")

    gateway = LLMGateway(primary_provider=groq_mock, fallback_provider=ollama_mock)
    with pytest.raises(RuntimeError) as exc_info:
        await gateway.generate_react_decision(
            goal="Check trends",
            tools_text="[]",
            state={},
        )
    assert "All configured LLM providers failed" in str(exc_info.value)

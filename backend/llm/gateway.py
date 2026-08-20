"""
BugPilot — LLM Gateway & Provider Orchestrator
================================================
Routes LLM calls to Groq (Primary) with automatic zero-quota failover to Ollama (Fallback).
Logs provider transitions securely without logging API keys, authorization headers, or secrets.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from backend.llm.base import BaseLLMProvider
from backend.llm.providers.groq import GroqProvider
from backend.llm.providers.ollama import OllamaProvider
from backend.llm.schemas import ReActAction, ReActDecision

logger = logging.getLogger("bugpilot.llm.gateway")


# ============================================================================
# REACT OUTPUT PARSER & VALIDATOR
# ============================================================================


def parse_react_decision(raw_text: str) -> Dict[str, Any]:
    """
    Robustly parses raw text into a valid ReAct decision dictionary.
    Handles:
    - Raw JSON
    - Markdown fenced code blocks (```json ... ```)
    - Surrounding conversational text
    - Strict validation: CALL_TOOL, DELEGATE, FINISH
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Cannot parse empty ReAct decision text.")

    cleaned = raw_text.strip()

    # Strip markdown code fences if wrapped
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    parsed_obj: Optional[Dict[str, Any]] = None

    # 1. Direct JSON parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            parsed_obj = data
    except Exception:
        pass

    # 2. Regex fallback for embedded JSON object
    if parsed_obj is None:
        match = re.search(r"(\{[\s\S]*\})", raw_text)
        if match:
            try:
                candidate = json.loads(match.group(1).strip())
                if isinstance(candidate, dict):
                    parsed_obj = candidate
            except Exception:
                pass

    if parsed_obj is None:
        raise ValueError(f"Could not extract valid JSON from LLM output: {raw_text[:200]}")

    # Validate against strict Pydantic model
    validated = ReActDecision.model_validate(parsed_obj)
    return validated.to_dict()


# ============================================================================
# LLM GATEWAY
# ============================================================================


class LLMGateway:
    """
    Unified LLM Gateway providing automatic provider failover:
    Primary: GroqProvider (llama-3.3-70b-versatile)
    Fallback: OllamaProvider (local llama3.1:8b)
    """

    def __init__(
        self,
        primary_provider: Optional[BaseLLMProvider] = None,
        fallback_provider: Optional[BaseLLMProvider] = None,
    ) -> None:
        self.primary = primary_provider or GroqProvider()
        self.fallback = fallback_provider or OllamaProvider()

    async def generate_react_decision(
        self,
        goal: str,
        tools_text: str,
        state: Dict[str, Any],
        available_agents: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Request ReAct decision with automatic Groq -> Ollama fallback.
        """
        agents_list = available_agents or [
            {"name": "Bug Analyst", "role": "Investigate bug details and specific bug records"},
            {"name": "Trend Analyst", "role": "Analyze creation/resolution velocity and trends"},
            {"name": "Risk Analyst", "role": "Analyze component risk and release readiness"},
        ]

        # 1. Try Primary Provider (Groq)
        try:
            logger.info("LLM provider=%s", self.primary.provider_name)
            decision = await self.primary.generate_react_decision(
                goal=goal,
                tools_text=tools_text,
                available_agents=agents_list,
                state=state,
            )
            if decision:
                return decision.to_dict()
        except Exception as primary_err:
            logger.warning(
                "Primary LLM provider (%s) failed: %s. Initiating automatic fallback.",
                self.primary.provider_name,
                primary_err,
            )

        # 2. Try Fallback Provider (Ollama)
        try:
            logger.info("LLM provider fallback=%s", self.fallback.provider_name)
            decision = await self.fallback.generate_react_decision(
                goal=goal,
                tools_text=tools_text,
                available_agents=agents_list,
                state=state,
            )
            if decision:
                return decision.to_dict()
        except Exception as fallback_err:
            logger.error(
                "Fallback LLM provider (%s) also failed: %s",
                self.fallback.provider_name,
                fallback_err,
            )
            raise RuntimeError(
                f"All configured LLM providers failed. Primary: {self.primary.provider_name}, Fallback: {self.fallback.provider_name}"
            ) from fallback_err

        return None

    async def generate_analysis(
        self,
        evidence: Any,
        question: str,
    ) -> Optional[str]:
        """
        Generate evidence-grounded final report with automatic Groq -> Ollama fallback.
        """
        # 1. Try Primary (Groq)
        try:
            logger.info("LLM provider=%s", self.primary.provider_name)
            result = await self.primary.generate_analysis(evidence=evidence, question=question)
            if result and result.strip():
                return result.strip()
        except Exception as primary_err:
            logger.warning(
                "Primary LLM provider (%s) analysis failed: %s. Initiating fallback.",
                self.primary.provider_name,
                primary_err,
            )

        # 2. Try Fallback (Ollama)
        try:
            logger.info("LLM provider fallback=%s", self.fallback.provider_name)
            result = await self.fallback.generate_analysis(evidence=evidence, question=question)
            if result and result.strip():
                return result.strip()
        except Exception as fallback_err:
            logger.warning(
                "Fallback LLM provider (%s) analysis failed: %s",
                self.fallback.provider_name,
                fallback_err,
            )

        return None

    def get_last_usage(self) -> Optional[Dict[str, Any]]:
        """Returns real token usage from primary provider if available."""
        if hasattr(self.primary, "get_last_usage"):
            return self.primary.get_last_usage()
        return None


# Global Gateway Singleton
default_gateway = LLMGateway()


async def generate_react_decision(
    goal: str,
    tools_text: str,
    state: Dict[str, Any],
    available_agents: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Convenience module function routing to default LLMGateway."""
    return await default_gateway.generate_react_decision(
        goal=goal,
        tools_text=tools_text,
        state=state,
        available_agents=available_agents,
    )


async def generate_analysis(
    evidence: Any,
    question: str,
) -> Optional[str]:
    """Convenience module function routing to default LLMGateway."""
    return await default_gateway.generate_analysis(
        evidence=evidence,
        question=question,
    )


def get_last_usage() -> Optional[Dict[str, Any]]:
    """Returns token usage metadata from the most recent LLM call."""
    return default_gateway.get_last_usage()

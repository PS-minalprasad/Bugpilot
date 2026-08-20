"""
BugPilot — Groq LLM Provider (PRIMARY)
========================================
High-throughput, low-latency primary LLM provider using Groq's OpenAI-compatible API.
Supports strict JSON output mode.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
import httpx

from backend.config import settings
from backend.llm.base import BaseLLMProvider
from backend.llm.schemas import ReActDecision
from backend.llm.prompts import (
    build_react_system_prompt,
    build_react_user_prompt,
    build_analysis_prompt,
)

logger = logging.getLogger("bugpilot.llm.groq")

GROQ_API_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
FALLBACK_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3.6-27b",
    "groq/compound-mini",
]

# Official Groq pricing table (USD per 1M tokens)
GROQ_MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "llama-3.3-70b-versatile": {"prompt_per_million": 0.59, "completion_per_million": 0.79},
    "llama-3.1-70b-versatile": {"prompt_per_million": 0.59, "completion_per_million": 0.79},
    "llama-3.1-8b-instant": {"prompt_per_million": 0.05, "completion_per_million": 0.08},
    "openai/gpt-oss-120b": {"prompt_per_million": 0.59, "completion_per_million": 0.79},
    "openai/gpt-oss-20b": {"prompt_per_million": 0.20, "completion_per_million": 0.20},
    "qwen/qwen3.6-27b": {"prompt_per_million": 0.20, "completion_per_million": 0.20},
}


def calculate_groq_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str = "llama-3.3-70b-versatile",
) -> float:
    """Calculates actual cost in USD based on official Groq pricing per model."""
    pricing = GROQ_MODEL_PRICING.get(
        model, {"prompt_per_million": 0.59, "completion_per_million": 0.79}
    )
    prompt_cost = (prompt_tokens / 1_000_000.0) * pricing["prompt_per_million"]
    comp_cost = (completion_tokens / 1_000_000.0) * pricing["completion_per_million"]
    return round(prompt_cost + comp_cost, 7)


class GroqProvider(BaseLLMProvider):
    """Groq LLM provider implementation with real token usage recording."""

    def __init__(self) -> None:
        self._last_usage: Optional[Dict[str, Any]] = None

    def get_last_usage(self) -> Optional[Dict[str, Any]]:
        """Returns real token usage from the most recent Groq API call, if available."""
        return self._last_usage

    @property
    def provider_name(self) -> str:
        return "groq"

    def _get_api_key(self) -> str:
        key = str(getattr(settings, "GROQ_API_KEY", "")).strip()
        if not key:
            raise RuntimeError("GROQ_API_KEY is not configured.")
        return key

    def _get_model_candidates(self) -> List[str]:
        configured = str(getattr(settings, "GROQ_MODEL", "")).strip()
        models = []
        if configured:
            models.append(configured)
        for m in FALLBACK_MODELS:
            if m not in models:
                models.append(m)
        return models

    def _get_timeout(self) -> float:
        try:
            timeout_val = float(getattr(settings, "LLM_TIMEOUT_SECONDS", 10.0))
        except (TypeError, ValueError):
            timeout_val = 10.0
        return max(1.0, min(timeout_val, 30.0))

    def _extract_content(self, data: Dict[str, Any]) -> str:
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("Groq response contained no choices.")
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if not content or not content.strip():
            raise RuntimeError("Groq response message content is empty.")
        return content.strip()

    async def generate_react_decision(
        self,
        goal: str,
        tools_text: str,
        available_agents: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> Optional[ReActDecision]:
        """Request next ReAct action from Groq with strict JSON output."""
        api_key = self._get_api_key()
        candidate_models = self._get_model_candidates()
        system_prompt = build_react_system_prompt()
        state_text = json.dumps(state, ensure_ascii=False, indent=2, default=str)
        user_prompt = build_react_user_prompt(goal, tools_text, available_agents, state_text)

        call_timeout = self._get_timeout()
        last_err: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=httpx.Timeout(call_timeout, connect=5.0)) as client:
            for model in candidate_models:
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.0,
                    "max_tokens": 512,
                }

                logger.info("Sending ReAct decision request to Groq. model=%s", model)
                try:
                    response = await client.post(
                        GROQ_API_BASE_URL,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )

                    if response.status_code in {400, 404, 429}:
                        logger.warning(
                            "Groq model '%s' returned HTTP %s. Trying next candidate model.",
                            model,
                            response.status_code,
                        )
                        last_err = RuntimeError(f"Groq API error HTTP {response.status_code}: {response.text[:200]}")
                        continue

                    if response.status_code != 200:
                        logger.error("Groq API returned HTTP %s for model %s", response.status_code, model)
                        raise RuntimeError(f"Groq API error HTTP {response.status_code}: {response.text[:300]}")

                    data = response.json()
                    usage_dict = data.get("usage", {})
                    if usage_dict:
                        p_tokens = int(usage_dict.get("prompt_tokens", 0))
                        c_tokens = int(usage_dict.get("completion_tokens", 0))
                        t_tokens = int(usage_dict.get("total_tokens", p_tokens + c_tokens))
                        self._last_usage = {
                            "prompt_tokens": p_tokens,
                            "completion_tokens": c_tokens,
                            "total_tokens": t_tokens,
                            "model": model,
                            "is_real": True,
                        }
                    raw_text = self._extract_content(data)
                    parsed_dict = json.loads(raw_text)
                    return ReActDecision.model_validate(parsed_dict)

                except Exception as exc:
                    last_err = exc
                    if "400" in str(exc) or "404" in str(exc) or "429" in str(exc):
                        continue
                    raise

        if last_err:
            raise last_err
        raise RuntimeError("Failed to generate ReAct decision from Groq candidate models.")

    async def generate_analysis(
        self,
        evidence: Any,
        question: str,
    ) -> Optional[str]:
        """Generate evidence-grounded final report using Groq."""
        api_key = self._get_api_key()
        candidate_models = self._get_model_candidates()
        evidence_text = json.dumps(evidence, ensure_ascii=False, indent=2, default=str)
        prompt_text = build_analysis_prompt(evidence_text, question)

        call_timeout = self._get_timeout()
        last_err: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=httpx.Timeout(call_timeout, connect=5.0)) as client:
            for model in candidate_models:
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "user", "content": prompt_text},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 1500,
                }

                logger.info("Sending report analysis request to Groq. model=%s", model)
                try:
                    response = await client.post(
                        GROQ_API_BASE_URL,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )

                    if response.status_code in {404, 429}:
                        logger.warning(
                            "Groq model '%s' returned HTTP %s for analysis. Trying next candidate model.",
                            model,
                            response.status_code,
                        )
                        last_err = RuntimeError(f"Groq API error HTTP {response.status_code}: {response.text[:200]}")
                        continue

                    if response.status_code != 200:
                        logger.error("Groq API returned HTTP %s for model %s", response.status_code, model)
                        raise RuntimeError(f"Groq API error HTTP {response.status_code}: {response.text[:300]}")

                    data = response.json()
                    usage_dict = data.get("usage", {})
                    if usage_dict:
                        p_tokens = int(usage_dict.get("prompt_tokens", 0))
                        c_tokens = int(usage_dict.get("completion_tokens", 0))
                        t_tokens = int(usage_dict.get("total_tokens", p_tokens + c_tokens))
                        self._last_usage = {
                            "prompt_tokens": p_tokens,
                            "completion_tokens": c_tokens,
                            "total_tokens": t_tokens,
                            "model": model,
                            "is_real": True,
                        }
                    return self._extract_content(data)

                except Exception as exc:
                    last_err = exc
                    if "404" in str(exc) or "429" in str(exc):
                        continue
                    raise

        if last_err:
            raise last_err
        raise RuntimeError("Failed to generate analysis from Groq candidate models.")

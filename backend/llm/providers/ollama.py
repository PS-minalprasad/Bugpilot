"""
BugPilot — Ollama LLM Provider (FALLBACK)
===========================================
Local fallback LLM provider using Ollama's local HTTP API (/api/chat).
Supports strict JSON output format without cloud API keys or external quotas.
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

logger = logging.getLogger("bugpilot.llm.ollama")


class OllamaProvider(BaseLLMProvider):
    """Local Ollama LLM provider implementation for automatic zero-quota fallback."""

    @property
    def provider_name(self) -> str:
        return "ollama"

    def _get_base_url(self) -> str:
        url = str(getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")).strip()
        if not url:
            url = "http://localhost:11434"
        return url.rstrip("/")

    def _get_model(self) -> str:
        model = str(getattr(settings, "OLLAMA_MODEL", "llama3.1:8b")).strip()
        return model if model else "llama3.1:8b"

    def _get_timeout(self) -> float:
        try:
            timeout_val = float(getattr(settings, "LLM_TIMEOUT_SECONDS", 15.0))
        except (TypeError, ValueError):
            timeout_val = 15.0
        return max(2.0, min(timeout_val, 60.0))

    def _extract_content(self, data: Dict[str, Any]) -> str:
        # /api/chat returns {"message": {"content": "..."}}
        message = data.get("message", {})
        content = message.get("content", "")
        if not content and "response" in data:
            content = data.get("response", "")
        if not content or not content.strip():
            raise RuntimeError("Ollama response content is empty.")
        return content.strip()

    async def generate_react_decision(
        self,
        goal: str,
        tools_text: str,
        available_agents: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> Optional[ReActDecision]:
        """Request next ReAct action from local Ollama with JSON output."""
        base_url = self._get_base_url()
        model = self._get_model()
        system_prompt = build_react_system_prompt()
        state_text = json.dumps(state, ensure_ascii=False, indent=2, default=str)
        user_prompt = build_react_user_prompt(goal, tools_text, available_agents, state_text)

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.0,
            },
        }

        call_timeout = self._get_timeout()
        logger.info("Sending ReAct decision request to Ollama fallback. url=%s model=%s", base_url, model)

        async with httpx.AsyncClient(timeout=httpx.Timeout(call_timeout, connect=3.0)) as client:
            response = await client.post(
                f"{base_url}/api/chat",
                json=payload,
            )

            if response.status_code != 200:
                logger.error("Ollama API returned HTTP %s", response.status_code)
                raise RuntimeError(f"Ollama API error HTTP {response.status_code}: {response.text[:300]}")

            data = response.json()
            raw_text = self._extract_content(data)
            parsed_dict = json.loads(raw_text)
            return ReActDecision.model_validate(parsed_dict)

    async def generate_analysis(
        self,
        evidence: Any,
        question: str,
    ) -> Optional[str]:
        """Generate evidence-grounded report using local Ollama."""
        base_url = self._get_base_url()
        model = self._get_model()
        evidence_text = json.dumps(evidence, ensure_ascii=False, indent=2, default=str)
        prompt_text = build_analysis_prompt(evidence_text, question)

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt_text},
            ],
            "stream": False,
            "options": {
                "temperature": 0.2,
            },
        }

        call_timeout = self._get_timeout()
        logger.info("Sending report analysis request to Ollama fallback. url=%s model=%s", base_url, model)

        async with httpx.AsyncClient(timeout=httpx.Timeout(call_timeout, connect=3.0)) as client:
            response = await client.post(
                f"{base_url}/api/chat",
                json=payload,
            )

            if response.status_code != 200:
                raise RuntimeError(f"Ollama analysis error HTTP {response.status_code}: {response.text[:300]}")

            data = response.json()
            return self._extract_content(data)

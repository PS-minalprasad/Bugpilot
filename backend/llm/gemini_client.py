"""
BugPilot — Gemini LLM Client
============================
Integrates Google Gemini API for evidence-grounded AI analysis.
Falls back gracefully to None on any error, timeout, or missing API key.
"""

from __future__ import annotations

import json
from typing import Any, Optional
import httpx

from backend.config import settings
from backend.core.logging import get_logger

logger = get_logger("bugpilot.llm.gemini")

GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _format_evidence(evidence: Any) -> str:
    """Formats evidence dictionary or list into a clean JSON/text string."""
    if isinstance(evidence, (dict, list)):
        try:
            return json.dumps(evidence, default=str, indent=2)
        except Exception:
            return str(evidence)
    return str(evidence)


async def generate_analysis(evidence: Any, question: str) -> Optional[str]:
    """
    Calls Google Gemini API to produce an evidence-grounded AI analysis.

    Returns:
        Generated markdown analysis string on success, or None on failure/missing key.
    """
    if not settings.GEMINI_API_KEY or not settings.GEMINI_API_KEY.strip():
        logger.debug("GEMINI_API_KEY is not configured; skipping Gemini call.")
        return None

    evidence_text = _format_evidence(evidence)

    system_instructions = (
        "You are BugPilot's AI engineering intelligence analyst.\n"
        "Your task is to provide an objective, evidence-grounded analysis based strictly on the provided data.\n\n"
        "STRICT GROUNDING RULES:\n"
        "1. Base your statements exclusively on the supplied evidence.\n"
        "2. Do NOT invent, assume, or fabricate any root cause, technical explanation, business impact, historical trend, or related issue not present in the evidence.\n"
        "3. If the evidence does not contain a confirmed root cause or business impact, explicitly state that the available data does not provide enough evidence.\n"
        "4. Be concise, direct, and factual."
    )

    user_content = (
        f"Question / Task: {question}\n\n"
        f"EVIDENCE:\n"
        f"```json\n{evidence_text}\n```\n\n"
        f"Provide the AI Analysis section for this inquiry following the grounding rules."
    )

    url = f"{GEMINI_API_BASE_URL}/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
    payload = {
        "systemInstruction": {
            "parts": [{"text": system_instructions}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_content}]
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 1024,
        }
    }

    call_timeout = min(getattr(settings, "LLM_TIMEOUT_SECONDS", 5.0), 5.0)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(call_timeout, connect=3.0)) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.warning(f"Gemini API returned status {resp.status_code}: {resp.text[:200]}")
                return None

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return None

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                return None

            text = parts[0].get("text", "").strip()
            return text if text else None

    except (httpx.TimeoutException, TimeoutError):
        logger.warning(f"Gemini API timed out after {call_timeout}s.")
        return None
    except Exception as err:
        logger.warning(f"Gemini API call failed: {err}")
        return None

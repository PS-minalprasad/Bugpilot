"""
BugPilot — Base LLM Provider Interface
========================================
Defines the abstract BaseLLMProvider contract that all LLM providers (Groq, Ollama) implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from backend.llm.schemas import ReActDecision


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers in BugPilot."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the human-readable name of the provider (e.g. 'groq', 'ollama')."""
        pass

    @abstractmethod
    async def generate_react_decision(
        self,
        goal: str,
        tools_text: str,
        available_agents: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> Optional[ReActDecision]:
        """
        Query the LLM to decide the next ReAct action (CALL_TOOL, DELEGATE, or FINISH).
        Must return a validated ReActDecision or raise an exception on failure.
        """
        pass

    @abstractmethod
    async def generate_analysis(
        self,
        evidence: Any,
        question: str,
    ) -> Optional[str]:
        """
        Generate an evidence-grounded final report or answer using the LLM.
        """
        pass

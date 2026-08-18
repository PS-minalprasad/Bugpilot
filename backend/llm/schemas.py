"""
BugPilot — LLM & ReAct Schemas
================================
Defines strict schemas and enums for ReAct actions, decisions, and provider responses.
Robustly handles tool name aliases and argument nesting.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class ReActAction(str, Enum):
    CALL_TOOL = "CALL_TOOL"
    DELEGATE = "DELEGATE"
    FINISH = "FINISH"


class ReActDecision(BaseModel):
    """
    Validated decision returned by the LLM in the ReAct reasoning loop.
    Strictly accepts only CALL_TOOL, DELEGATE, or FINISH.
    """
    action: ReActAction
    tool_name: Optional[str] = Field(
        default=None,
        description="Name of the MCP tool to call (required when action=CALL_TOOL)"
    )
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to pass to the MCP tool"
    )
    agent: Optional[str] = Field(
        default=None,
        description="Target specialist agent name (required when action=DELEGATE)"
    )
    task: Optional[str] = Field(
        default=None,
        description="Task instructions for specialist agent (when action=DELEGATE)"
    )
    final_answer: Optional[str] = Field(
        default=None,
        description="Final answer text if model decides to conclude immediately (when action=FINISH)"
    )

    @model_validator(mode="before")
    @classmethod
    def extract_flexible_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        d = dict(data)

        # Normalize tool_name aliases
        if not d.get("tool_name"):
            for alt in ["tool", "name", "toolName", "function"]:
                if d.get(alt):
                    d["tool_name"] = d[alt]
                    break

        # Normalize arguments aliases
        args = d.get("arguments")
        if not isinstance(args, dict):
            for alt in ["parameters", "params", "args", "input"]:
                if isinstance(d.get(alt), dict):
                    args = d[alt]
                    break
        if not isinstance(args, dict):
            args = {}

        # If arguments was provided or not, capture any top-level tool parameter keys
        known_system_keys = {
            "action", "tool", "tool_name", "name", "toolName", "function",
            "arguments", "parameters", "params", "args", "input",
            "agent", "task", "final_answer"
        }
        for k, v in d.items():
            if k not in known_system_keys and k not in args:
                args[k] = v

        d["arguments"] = args
        return d

    @field_validator("action", mode="before")
    @classmethod
    def normalize_action(cls, v: Any) -> ReActAction:
        if isinstance(v, ReActAction):
            return v
        s = str(v).strip().upper()
        # Common aliases
        if s in {"TOOL", "TOOL_CALL", "EXECUTE_TOOL", "CALL_TOOL"}:
            return ReActAction.CALL_TOOL
        if s in {"DELEGATE", "DELEGATE_AGENT", "AGENT"}:
            return ReActAction.DELEGATE
        if s in {"FINISH", "COMPLETE", "DONE", "STOP"}:
            return ReActAction.FINISH
        raise ValueError(f"Invalid ReAct action: '{v}'. Must be CALL_TOOL, DELEGATE, or FINISH.")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary compatible with orchestrator consumption."""
        data: Dict[str, Any] = {"action": self.action.value}
        if self.action == ReActAction.CALL_TOOL:
            data["tool_name"] = self.tool_name or ""
            data["tool"] = self.tool_name or ""
            data["arguments"] = self.arguments or {}
        elif self.action == ReActAction.DELEGATE:
            data["agent"] = self.agent or ""
            data["task"] = self.task or ""
            data["arguments"] = self.arguments or {}
        elif self.action == ReActAction.FINISH:
            if self.final_answer:
                data["final_answer"] = self.final_answer
        return data


class LLMResponse(BaseModel):
    """Generic structured response from any LLM provider."""
    content: str
    provider: str
    model: str
    raw_response: Optional[Dict[str, Any]] = None

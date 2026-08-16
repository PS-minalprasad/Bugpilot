"""
BugPilot — Exception Hierarchy
================================
All custom exceptions for the application.

Design principles:
  - Every exception carries a human-readable ``detail`` message.
  - HTTP status codes are defined at the exception level so FastAPI handlers
    can map them without any coupling to HTTP concepts inside the domain.
  - No exception class leaks implementation secrets.
"""

from __future__ import annotations

from typing import Any


# =============================================================================
# Base
# =============================================================================

class BugPilotError(Exception):
    """Root exception for all BugPilot application errors."""

    http_status: int = 500
    error_code: str = "BUGPILOT_ERROR"

    def __init__(self, detail: str = "An unexpected error occurred.", **context: Any) -> None:
        super().__init__(detail)
        self.detail = detail
        self.context = context

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(detail={self.detail!r}, context={self.context})"


# =============================================================================
# Configuration
# =============================================================================

class ConfigurationError(BugPilotError):
    """Raised when application configuration is invalid or missing."""
    http_status = 500
    error_code = "CONFIGURATION_ERROR"


# =============================================================================
# Data / Provider
# =============================================================================

class DataProviderError(BugPilotError):
    """Raised when the data provider fails to return data."""
    http_status = 503
    error_code = "DATA_PROVIDER_ERROR"


class BugNotFoundError(BugPilotError):
    """Raised when a requested bug ID does not exist."""
    http_status = 404
    error_code = "BUG_NOT_FOUND"


class SprintNotFoundError(BugPilotError):
    """Raised when a requested sprint ID does not exist."""
    http_status = 404
    error_code = "SPRINT_NOT_FOUND"


# =============================================================================
# MCP Layer
# =============================================================================

class MCPError(BugPilotError):
    """Root MCP protocol error."""
    http_status = 502
    error_code = "MCP_ERROR"


class MCPToolNotFoundError(MCPError):
    """Raised when a requested MCP tool is not registered."""
    http_status = 404
    error_code = "MCP_TOOL_NOT_FOUND"


class MCPToolExecutionError(MCPError):
    """Raised when an MCP tool call raises an exception."""
    http_status = 502
    error_code = "MCP_TOOL_EXECUTION_ERROR"


class MCPConnectionError(MCPError):
    """Raised when the MCP client cannot connect to the server."""
    http_status = 503
    error_code = "MCP_CONNECTION_ERROR"


# =============================================================================
# Agent Layer
# =============================================================================

class AgentError(BugPilotError):
    """Root agent error."""
    http_status = 500
    error_code = "AGENT_ERROR"


class AgentExecutionError(AgentError):
    """Raised when an agent fails during execution."""
    http_status = 500
    error_code = "AGENT_EXECUTION_ERROR"


class AgentTimeoutError(AgentError):
    """Raised when an agent exceeds its allowed execution time."""
    http_status = 504
    error_code = "AGENT_TIMEOUT"


class OrchestratorError(AgentError):
    """Raised when the orchestrator encounters a fatal planning error."""
    http_status = 500
    error_code = "ORCHESTRATOR_ERROR"


# =============================================================================
# LLM Layer
# =============================================================================

class LLMError(BugPilotError):
    """Root LLM provider error."""
    http_status = 502
    error_code = "LLM_ERROR"


class LLMTimeoutError(LLMError):
    """Raised when the LLM call times out."""
    http_status = 504
    error_code = "LLM_TIMEOUT"


class LLMOutputParseError(LLMError):
    """Raised when the LLM output cannot be parsed into the expected schema."""
    http_status = 502
    error_code = "LLM_OUTPUT_PARSE_ERROR"


# =============================================================================
# API / Validation
# =============================================================================

class ValidationError(BugPilotError):
    """Raised when request input fails domain-level validation."""
    http_status = 422
    error_code = "VALIDATION_ERROR"


class NotFoundError(BugPilotError):
    """Generic 404."""
    http_status = 404
    error_code = "NOT_FOUND"


# =============================================================================
# Auth & Security
# =============================================================================

class AuthenticationError(BugPilotError):
    """Raised when user authentication fails or token is invalid."""
    http_status = 401
    error_code = "AUTHENTICATION_ERROR"


class AuthorizationError(BugPilotError):
    """Raised when user lacks permission/role or tenant isolation fails."""
    http_status = 403
    error_code = "AUTHORIZATION_ERROR"


"""
BugPilot — Application Configuration
=====================================
All settings are loaded from environment variables.
Secrets must NEVER be hardcoded here.
Copy .env.example → .env and fill in values.
"""

from __future__ import annotations

from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables / .env file.

    Priority (highest → lowest):
      1. Shell environment variables
      2. .env file in working directory
      3. Defaults defined here
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -------------------------------------------------------------------------
    # Application Identity
    # -------------------------------------------------------------------------
    APP_NAME: str = "BugPilot"
    APP_DESCRIPTION: str = "AI-Powered Engineering Bug Intelligence Agent"
    APP_VERSION: str = "1.0.0"

    # -------------------------------------------------------------------------
    # Runtime Environment
    # -------------------------------------------------------------------------
    ENV: str = "development"
    DEBUG: bool = True

    # -------------------------------------------------------------------------
    # Server
    # -------------------------------------------------------------------------
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    API_PREFIX: str = "/api"

    # -------------------------------------------------------------------------
    # CORS — comma-separated string in env, list here
    # -------------------------------------------------------------------------
    CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"  # "text" | "json"

    # -------------------------------------------------------------------------
    # Database (Phase 18)
    # -------------------------------------------------------------------------
    DATABASE_URL: str = "sqlite:///./bugpilot.db"

    # -------------------------------------------------------------------------
    # Auth & Security (Phase 15)
    # -------------------------------------------------------------------------
    JWT_SECRET: str = "bugpilot-super-secret-jwt-key-2026-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # -------------------------------------------------------------------------
    # Data & Providers (Phase 14)
    # -------------------------------------------------------------------------
    PROVIDER_MODE: str = "postgres"  # "postgres" | "synthetic"
    DATA_LABEL: str = "PostgreSQL"

    # -------------------------------------------------------------------------
    # LLM (Phase 6)
    # -------------------------------------------------------------------------
    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # -------------------------------------------------------------------------
    # AI Guardrail Execution Limits (Phase 21)
    # -------------------------------------------------------------------------
    MAX_AGENT_STEPS: int = 5
    MAX_MCP_TOOL_CALLS: int = 10
    MAX_RETRIES: int = 3
    TOOL_TIMEOUT_SECONDS: float = 30.0
    LLM_TIMEOUT_SECONDS: float = 30.0
    MAX_USER_QUERY_LENGTH: int = 2000

    # -------------------------------------------------------------------------
    # MCP (Phase 4) — placeholder, not used in Phase 1
    # -------------------------------------------------------------------------
    MCP_SERVER_HOST: str = "127.0.0.1"
    MCP_SERVER_PORT: int = 8001

    # -------------------------------------------------------------------------
    # Validators
    # -------------------------------------------------------------------------
    @field_validator("ENV")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "test"}
        if v not in allowed:
            raise ValueError(f"ENV must be one of {allowed}, got: {v!r}")
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}, got: {v!r}")
        return upper

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    @property
    def data_label(self) -> str:
        """Return the database data source label."""
        if self.DATABASE_URL.startswith("sqlite") and self.DATA_LABEL.lower() == "sqlite":
            return "SQLite"
        return self.DATA_LABEL

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.ENV == "development"

    @property
    def openapi_url(self) -> str | None:
        """Disable OpenAPI docs in production."""
        return None if self.is_production else "/openapi.json"


def get_settings() -> Settings:
    """Return the application settings singleton."""
    return _settings


# Singleton — instantiated once at module load time.
_settings = Settings()
settings = _settings

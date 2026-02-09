"""
Configuration management for GOrchestrator.
Uses pydantic-settings for type-safe configuration with environment variable support.
Supports separate configurations for Orchestrator (Manager) and Worker agents.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ============================================================
    # ORCHESTRATOR (Manager Agent) Configuration
    # ============================================================
    ORCHESTRATOR_MODEL: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="LLM model for the Manager/Orchestrator agent",
    )

    ORCHESTRATOR_API_BASE: str = Field(
        default="http://127.0.0.1:8045",
        description="API base URL for the Orchestrator LLM",
    )

    ORCHESTRATOR_API_KEY: str = Field(
        default="sk-dummy-orchestrator-key",
        description="API key for the Orchestrator LLM",
    )

    # ============================================================
    # WORKER (Mini-SWE-GOCore) Configuration
    # ============================================================
    WORKER_MODEL: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="LLM model passed to the Worker subprocess",
    )

    WORKER_PROFILE: str = Field(
        default="live",
        description="Configuration profile for the Worker agent (e.g., 'live', 'swebench', 'custom')",
    )

    AGENT_PATH: str = Field(
        default="../Mini-SWE-GOCore",
        description="Path to the Mini-SWE-GOCore agent folder",
    )

    # Legacy proxy settings (used by Worker subprocess)
    PROXY_URL: str = Field(
        default="http://127.0.0.1:8045",
        description="LiteLLM proxy URL for Worker",
    )

    PROXY_KEY: str = Field(
        default="sk-dummy-proxy-key",
        description="API key for the Worker proxy",
    )

    BYPASS_KEY: str = Field(
        default="sk-dummy",
        description="Bypass key for LiteLLM direct API access",
    )

    # ============================================================
    # Application Settings
    # ============================================================
    VERBOSE_WORKER: bool = Field(
        default=False,
        description="Show detailed Worker output (vs summary only)",
    )

    MAX_WORKER_ITERATIONS: int = Field(
        default=5,
        description="Maximum Worker retry iterations per task",
    )

    WORKER_TIMEOUT: int = Field(
        default=600,
        description="Maximum time in seconds for a Worker task before timeout (0 = no timeout)",
    )

    @property
    def agent_path_resolved(self) -> Path:
        """Return the resolved absolute path to the agent folder."""
        path = Path(self.AGENT_PATH)
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()

    def get_agent_env(self) -> dict[str, str]:
        """
        Build environment variables to inject into the agent subprocess.
        These are required for Mini-SWE-GOCore to communicate with LiteLLM proxy.
        """
        return {
            "MINI_API_BASE": self.PROXY_URL,
            "ANTHROPIC_API_KEY": self.BYPASS_KEY,
            "OPENAI_API_KEY": self.BYPASS_KEY,
            "LITELLM_API_KEY": self.PROXY_KEY,
        }

    def get_orchestrator_config(self) -> dict[str, str]:
        """Get configuration for the Orchestrator LLM calls."""
        return {
            "model": self.ORCHESTRATOR_MODEL,
            "api_base": self.ORCHESTRATOR_API_BASE,
            "api_key": self.ORCHESTRATOR_API_KEY,
        }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

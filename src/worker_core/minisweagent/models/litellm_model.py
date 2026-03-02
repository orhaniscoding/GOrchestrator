"""LiteLLM model wrapper with custom proxy support.

Supports:
- MINI_API_BASE: Custom API endpoint (e.g., http://localhost:8080/v1)
- MINI_API_KEY: Custom API key for proxy
- MINI_API_TIMEOUT: Request timeout in seconds
"""

import json
import logging
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

import litellm
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from minisweagent.models import GLOBAL_MODEL_STATS
from minisweagent.models.utils.cache_control import set_cache_control

logger = logging.getLogger("litellm_model")


@dataclass
class LitellmModelConfig:
    """Configuration for LiteLLM model."""

    model_name: str
    """Model name (e.g., 'gpt-4o', 'claude-3-opus', 'ollama/llama2')"""

    model_kwargs: dict[str, Any] = field(default_factory=dict)
    """Additional kwargs passed to litellm.completion()"""

    litellm_model_registry: Path | str | None = field(
        default_factory=lambda: os.getenv("LITELLM_MODEL_REGISTRY_PATH")
    )
    """Path to custom model registry JSON file"""

    set_cache_control: Literal["default_end"] | None = None
    """Set explicit cache control markers (for Anthropic models)"""

    cost_tracking: Literal["default", "ignore_errors"] = field(
        default_factory=lambda: os.getenv("MSWEA_COST_TRACKING", os.getenv("MINI_COST_TRACKING", "default"))
    )
    """Cost tracking mode: 'default' or 'ignore_errors'"""

    # === CUSTOM PROXY SUPPORT ===
    api_base: Optional[str] = field(
        default_factory=lambda: os.getenv("MINI_API_BASE")
    )
    """Custom API base URL (e.g., http://localhost:8080/v1).
    Set via MINI_API_BASE env var or in config YAML.
    No vendor validation - requests go directly to this URL."""

    api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("MINI_API_KEY")
    )
    """Custom API key for proxy. Set via MINI_API_KEY env var."""

    api_version: Optional[str] = field(
        default_factory=lambda: os.getenv("MINI_API_VERSION")
    )
    """API version (for Azure, etc.). Set via MINI_API_VERSION env var."""

    timeout: int = field(
        default_factory=lambda: int(os.getenv("MINI_API_TIMEOUT", "120"))
    )
    """Request timeout in seconds. Default: 120"""


class LitellmModel:
    """LiteLLM model wrapper with proxy support."""

    def __init__(self, *, config_class: Callable = LitellmModelConfig, **kwargs):
        self.config = config_class(**kwargs)
        self.cost = 0.0
        self.n_calls = 0

        # Register custom models if provided
        if self.config.litellm_model_registry and Path(self.config.litellm_model_registry).is_file():
            litellm.utils.register_model(
                json.loads(Path(self.config.litellm_model_registry).read_text())
            )

        # Log proxy configuration
        if self.config.api_base:
            logger.info(f"Using custom API base: {self.config.api_base}")
        if self.config.api_key:
            logger.debug("Using custom API key (MINI_API_KEY)")

    def _get_completion_kwargs(self) -> dict[str, Any]:
        """Build kwargs for litellm.completion() including proxy settings."""
        kwargs = dict(self.config.model_kwargs)

        # Custom proxy settings - no vendor validation
        if self.config.api_base:
            kwargs["api_base"] = self.config.api_base
        if self.config.api_key:
            kwargs["api_key"] = self.config.api_key
        if self.config.api_version:
            kwargs["api_version"] = self.config.api_version
        if self.config.timeout:
            kwargs["timeout"] = self.config.timeout

        return kwargs

    @retry(
        reraise=True,
        stop=stop_after_attempt(int(os.getenv("MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT", "10"))),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        retry=retry_if_not_exception_type(
            (
                litellm.exceptions.UnsupportedParamsError,
                litellm.exceptions.NotFoundError,
                litellm.exceptions.PermissionDeniedError,
                litellm.exceptions.ContextWindowExceededError,
                litellm.exceptions.APIError,
                litellm.exceptions.AuthenticationError,
                KeyboardInterrupt,
            )
        ),
    )
    def _parse_provider_model(self, model_name: str) -> tuple[str, Optional[str]]:
        """Parse 'provider/model' format and return (model, provider).

        Examples:
            'anthropic/claude-thinking' -> ('claude-thinking', 'anthropic')
            'openai/gpt-4' -> ('gpt-4', 'openai')
            'gpt-4o' -> ('gpt-4o', None)
        """
        if "/" in model_name:
            provider, model_real_name = model_name.split("/", 1)
            return model_real_name, provider
        return model_name, None

    @staticmethod
    def _detect_provider(model_name: str) -> str:
        """Detect provider from model name for proxy routing."""
        name = model_name.lower()
        if any(k in name for k in ("claude", "opus", "sonnet", "haiku")):
            return "anthropic"
        if any(k in name for k in ("gemini", "palm")):
            return "gemini"
        return "openai"

    def _query(self, messages: list[dict[str, str]], **kwargs):
        """Execute LLM query with retry logic and provider-aware routing."""
        completion_kwargs = self._get_completion_kwargs() | kwargs

        model_name, explicit_provider = self._parse_provider_model(self.config.model_name)

        if self.config.api_base:
            # Proxy mode: detect provider so LiteLLM sends native format
            provider = explicit_provider or self._detect_provider(model_name)
            completion_kwargs["custom_llm_provider"] = provider
            logger.debug(f"Proxy mode: '{model_name}' via '{provider}' to {self.config.api_base}")
        elif explicit_provider:
            completion_kwargs["custom_llm_provider"] = explicit_provider

        try:
            return litellm.completion(
                model=model_name,
                messages=messages,
                **completion_kwargs,
            )
        except litellm.exceptions.AuthenticationError as e:
            if self.config.api_base:
                e.message += f" (API Base: {self.config.api_base})"
            e.message += " Set MINI_API_KEY env var or use `mini-extra config set MINI_API_KEY <key>`."
            raise e

    def query(self, messages: list[dict[str, str]], **kwargs) -> dict:
        """Query the model and return response with content."""
        if self.config.set_cache_control:
            messages = set_cache_control(messages, mode=self.config.set_cache_control)

        response = self._query(
            [{"role": msg["role"], "content": msg["content"]} for msg in messages],
            **kwargs
        )

        # Cost calculation
        try:
            cost = litellm.cost_calculator.completion_cost(response, model=self.config.model_name)
            if cost <= 0.0:
                raise ValueError(f"Cost must be > 0.0, got {cost}")
        except Exception as e:
            cost = 0.0
            if self.config.cost_tracking != "ignore_errors":
                msg = (
                    f"Error calculating cost for model {self.config.model_name}: {e}. "
                    "Set cost_tracking: 'ignore_errors' in config or "
                    "export MINI_COST_TRACKING='ignore_errors' to ignore."
                )
                logger.critical(msg)
                raise RuntimeError(msg) from e

        self.n_calls += 1
        self.cost += cost
        GLOBAL_MODEL_STATS.add(cost)

        return {
            "content": response.choices[0].message.content or "",  # type: ignore
            "extra": {
                "response": response.model_dump(),
            },
        }

    def get_template_vars(self) -> dict[str, Any]:
        """Get template variables for Jinja rendering."""
        return asdict(self.config) | {"n_model_calls": self.n_calls, "model_cost": self.cost}

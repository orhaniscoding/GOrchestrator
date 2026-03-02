"""
Configuration management for GOrchestrator.
Uses pydantic-settings for type-safe configuration with environment variable support.
Supports separate configurations for Orchestrator (Manager) and Worker agents.
LiteLLM-based routing: detects model provider for LiteLLM's custom_llm_provider parameter.
"""

import atexit
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache  # kept for backward compat if used elsewhere
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

SANITIZE_RE = re.compile(r"[^a-zA-Z0-9_-]")

# Pattern to detect API keys in error messages (multiple providers)
_API_KEY_RE = re.compile(r'(sk-[a-zA-Z0-9]{4})[a-zA-Z0-9]{8,}|'
                         r'(sk-ant-[a-zA-Z0-9]{4})[a-zA-Z0-9]{8,}|'
                         r'(ant-api[a-zA-Z0-9]{4})[a-zA-Z0-9]{8,}|'
                         r'(key-[a-zA-Z0-9]{4})[a-zA-Z0-9]{8,}|'
                         r'(AIza[a-zA-Z0-9]{4})[a-zA-Z0-9]{8,}|'
                         r'(or-[a-zA-Z0-9]{4})[a-zA-Z0-9]{8,}|'
                         r'(xai-[a-zA-Z0-9]{4})[a-zA-Z0-9]{8,}|'
                         r'(Bearer\s+[a-zA-Z0-9]{4})[a-zA-Z0-9]{8,}|'
                         r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-)[0-9a-f]{12}')


def mask_api_keys(text: str) -> str:
    """Mask API keys in text to prevent credential leakage in logs/history."""
    if not text:
        return text
    return _API_KEY_RE.sub(lambda m: next(g for g in m.groups() if g) + "****", text)


def sanitize_name(name: str) -> str:
    """Sanitize a name to only contain [a-zA-Z0-9_-]."""
    return SANITIZE_RE.sub("-", name)


# Provider detection keywords
_ANTHROPIC_KEYWORDS = ("claude", "opus", "sonnet", "haiku")
_GOOGLE_KEYWORDS = ("gemini", "palm")


def call_litellm(
    model: str,
    messages: list[dict],
    api_base: str | None = None,
    api_key: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: int = 120,
) -> tuple[str, float]:
    """Shared LiteLLM completion call for sub-managers and LLM pools.

    Handles provider detection, kwargs building, and response extraction.
    Manager agent uses its own _call_llm() for tool-use and retry support.

    Returns:
        Tuple of (content_string, duration_seconds).

    Raises:
        Exception: On LLM API errors (caller should handle).
    """
    import time
    import litellm as _litellm

    start_time = time.time()
    model_name = strip_provider_prefix(model)
    provider = detect_provider(model)

    kwargs: dict = {
        "model": model_name,
        "messages": messages,
        "custom_llm_provider": provider,
        "timeout": timeout,
        "max_tokens": max_tokens or 4096,
    }
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key
    if temperature is not None:
        kwargs["temperature"] = temperature

    response = _litellm.completion(**kwargs)
    content = response.choices[0].message.content or ""
    duration = time.time() - start_time
    return content, duration


_SUB_MANAGER_PROFILES_DIR = Path(__file__).resolve().parent / "sub_manager_profiles"

# YAML profile cache: path -> (mtime, parsed_data)
_profile_cache: dict[str, tuple[float, dict]] = {}


def _load_yaml_cached(profile_path: Path) -> dict:
    """Load a YAML file with mtime-based caching."""
    key = str(profile_path)
    try:
        mtime = profile_path.stat().st_mtime
    except OSError:
        _profile_cache.pop(key, None)
        raise
    cached = _profile_cache.get(key)
    if cached and cached[0] == mtime:
        return cached[1].copy()
    with open(profile_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    _profile_cache[key] = (mtime, data)
    return data.copy()


def validate_profile_name(name: str) -> str:
    """Validate a profile name to prevent path traversal attacks.

    Rejects names containing '..' or path separators that could escape
    the profiles directory.

    Raises:
        ValueError: If the name contains path traversal characters.
    """
    if ".." in name or "/" in name or "\\" in name or "\0" in name:
        raise ValueError(f"Invalid profile name: {name!r} (path traversal characters not allowed)")
    return name


def load_sub_manager_profile(profile_path: Path) -> dict:
    """
    Load sub-manager configuration from a YAML profile file (cached).

    Args:
        profile_path: Path to the YAML profile file.

    Returns:
        dict with keys: name, description, perspective, model, api_base, api_key,
        system_prompt, temperature, max_tokens, thinking

    Raises:
        Exception: If YAML parsing fails.
    """
    data = _load_yaml_cached(profile_path)

    config = {
        "name": data.get("name", profile_path.stem),
        "description": data.get("description", ""),
        "perspective": data.get("perspective", ""),
        "model": data.get("model", ""),
        "api_base": data.get("api_base"),
        "api_key": data.get("api_key"),
        "system_prompt": data.get("system_prompt"),
        "temperature": data.get("temperature"),
        "max_tokens": data.get("max_tokens"),
        "thinking": data.get("thinking"),
    }

    logger.info(f"Loaded sub-manager profile from {profile_path}")
    return config


def load_manager_profile(profile_path: Path) -> dict:
    """
    Load manager configuration from a YAML profile file (cached).

    Args:
        profile_path: Path to the YAML profile file.

    Returns:
        dict with keys: model, api_base, api_key, system_prompt, temperature, max_tokens, thinking

    Raises:
        ValueError: If required fields are missing.
        Exception: If YAML parsing fails.
    """
    data = _load_yaml_cached(profile_path)
    
    # Required fields (api_key is optional - falls back to ORCHESTRATOR_API_KEY)
    required_fields = ["model", "api_base"]
    missing = [field for field in required_fields if not data.get(field)]
    if missing:
        raise ValueError(f"Manager profile missing required fields: {missing}")

    # Build config dict with all fields
    config = {
        "model": data["model"],
        "api_base": data["api_base"],
        "api_key": data.get("api_key", ""),
        "system_prompt": data.get("system_prompt"),
        "temperature": data.get("temperature"),
        "max_tokens": data.get("max_tokens"),
        "thinking": data.get("thinking"),
    }
    
    logger.info(f"Loaded manager profile from {profile_path}")
    return config


def detect_provider(model_name: str) -> str:
    """Detect the API provider from model name.

    Returns 'anthropic', 'google', or 'openai' (default).
    Explicit 'provider/model' prefix takes priority.
    """
    # Explicit prefix: "anthropic/claude-opus-4" → anthropic
    if "/" in model_name:
        provider = model_name.split("/", 1)[0].lower()
        if provider in ("anthropic", "openai", "google", "vertex_ai"):
            return provider
    name = model_name.lower()
    if any(k in name for k in _ANTHROPIC_KEYWORDS):
        return "anthropic"
    if any(k in name for k in _GOOGLE_KEYWORDS):
        return "google"
    return "openai"


def strip_provider_prefix(model_name: str) -> str:
    """Remove provider prefix from model name (e.g. 'anthropic/claude-opus-4' → 'claude-opus-4')."""
    for prefix in ("openai/", "vertex_ai/", "anthropic/", "google/"):
        if model_name.startswith(prefix):
            return model_name[len(prefix):]
    return model_name

# Resolve .env path relative to project root (where main.py lives)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ============================================================
    # ORCHESTRATOR (Manager Agent) Configuration
    # ============================================================
    MANAGER_PROFILE: str = Field(
        default="default",
        description="Manager configuration profile (e.g., 'default', 'advanced', 'custom'). Loads from src/core/manager_profiles/<profile>.yaml",
    )

    ORCHESTRATOR_MODEL: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="LLM model for the Manager/Orchestrator agent (legacy, used only if MANAGER_PROFILE not set)",
    )

    ORCHESTRATOR_API_BASE: str = Field(
        default="http://127.0.0.1:8045",
        description="API base URL for the Orchestrator LLM (legacy, used only if MANAGER_PROFILE not set)",
    )

    ORCHESTRATOR_API_KEY: str = Field(
        default="sk-dummy-orchestrator-key",
        description="API key for the Orchestrator LLM (legacy, used only if MANAGER_PROFILE not set)",
    )

    # Runtime Override Fields (for /manager commands, NOT persisted to .env)
    MANAGER_MODEL_OVERRIDE: str = Field(
        default="",
        description="Override manager model at runtime (not persisted to .env)",
    )

    MANAGER_API_BASE_OVERRIDE: str = Field(
        default="",
        description="Override manager API base at runtime (not persisted)",
    )

    MANAGER_API_KEY_OVERRIDE: str = Field(
        default="",
        description="Override manager API key at runtime (not persisted)",
    )

    MANAGER_TEMP_OVERRIDE: str = Field(
        default="",
        description="Override manager temperature at runtime (not persisted)",
    )

    MANAGER_TOKENS_OVERRIDE: str = Field(
        default="",
        description="Override manager max tokens at runtime (not persisted)",
    )

    MANAGER_RULES_FILE: str = Field(
        default="rules.yaml",
        description="Manager rules configuration file (relative to manager_profiles/)",
    )

    # ============================================================
    # WORKER (Integrated Worker Core) Configuration
    # ============================================================
    WORKER_MODEL: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="LLM model passed to the Worker subprocess",
    )

    WORKER_PROFILE: str = Field(
        default="livesweagent",
        description="Configuration profile for the Worker agent (e.g., 'livesweagent', 'live', 'custom')",
    )

    AGENT_PATH: str = Field(
        default="src/worker_core",
        description="Path to the integrated worker core (Mini-SWE-GOCore engine)",
    )

    # Proxy settings (used by Worker subprocess)
    PROXY_URL: str = Field(
        default="http://127.0.0.1:8045",
        description="API proxy URL for Worker",
    )

    PROXY_KEY: str = Field(
        default="sk-dummy-proxy-key",
        description="API key for the Worker proxy",
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

    MAX_CONVERSATION_MESSAGES: int = Field(
        default=100,
        description="Maximum number of messages to keep in conversation history (system message excluded)",
    )

    @property
    def agent_path_resolved(self) -> Path:
        """Return the resolved absolute path to the agent folder."""
        path = Path(self.AGENT_PATH)
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()

    def get_agent_env(self) -> dict[str, str]:
        """Build environment variables for the Worker subprocess.

        Only MINI_API_BASE and MINI_API_KEY are needed.
        LiteLLM in Mini-SWE-GOCore handles provider routing natively.
        """
        proxy = self.PROXY_URL.rstrip("/")
        return {
            "MINI_API_BASE": proxy,
            "MINI_API_KEY": self.PROXY_KEY,
        }

    def get_manager_config(self) -> dict[str, Any]:
        """
        Get manager configuration from profile YAML or fall back to ORCHESTRATOR_* env vars.

        Configuration Precedence (highest to lowest):
            1. Runtime overrides (MANAGER_*_OVERRIDE fields, set via /manager commands)
            2. MANAGER_PROFILE YAML file (src/core/manager_profiles/<profile>.yaml)
            3. ORCHESTRATOR_* environment variables (backward compatibility)
            4. Default values in Field() definitions
        """
        # Try profile YAML first
        if self.MANAGER_PROFILE:
            validate_profile_name(self.MANAGER_PROFILE)
            profile_path = _PROJECT_ROOT / "src/core/manager_profiles" / f"{self.MANAGER_PROFILE}.yaml"
            if profile_path.exists():
                try:
                    config = load_manager_profile(profile_path)
                    
                    # Load rules file if specified
                    if config.get("rules_file"):
                        rules_path = _PROJECT_ROOT / "src/core/manager_profiles" / config["rules_file"]
                        if rules_path.exists():
                            try:
                                with open(rules_path, "r", encoding="utf-8") as f:
                                    config["rules"] = yaml.safe_load(f)
                            except Exception as e:
                                logger.warning(f"Failed to load manager rules '{config['rules_file']}': {e}")
                    
                    # Fallback: if profile api_key is empty, use ORCHESTRATOR_API_KEY
                    if not config.get("api_key"):
                        config["api_key"] = self.ORCHESTRATOR_API_KEY

                    # Apply runtime overrides (highest priority)
                    if self.MANAGER_MODEL_OVERRIDE:
                        config["model"] = self.MANAGER_MODEL_OVERRIDE
                    if self.MANAGER_API_BASE_OVERRIDE:
                        config["api_base"] = self.MANAGER_API_BASE_OVERRIDE
                    if self.MANAGER_API_KEY_OVERRIDE:
                        config["api_key"] = self.MANAGER_API_KEY_OVERRIDE
                    if self.MANAGER_TEMP_OVERRIDE:
                        try:
                            config["temperature"] = float(self.MANAGER_TEMP_OVERRIDE)
                        except ValueError:
                            pass
                    if self.MANAGER_TOKENS_OVERRIDE:
                        try:
                            config["max_tokens"] = int(self.MANAGER_TOKENS_OVERRIDE)
                        except ValueError:
                            pass
                    
                    return config
                except Exception as e:
                    logger.warning(f"Failed to load manager profile '{self.MANAGER_PROFILE}': {e}. Falling back to ORCHESTRATOR_* vars.")
        
        # Backward compatible: use ORCHESTRATOR_* variables with runtime overrides
        config = {
            "model": self.MANAGER_MODEL_OVERRIDE or self.ORCHESTRATOR_MODEL,
            "api_base": self.MANAGER_API_BASE_OVERRIDE or self.ORCHESTRATOR_API_BASE,
            "api_key": self.MANAGER_API_KEY_OVERRIDE or self.ORCHESTRATOR_API_KEY,
            "system_prompt": None,  # Will use default from ManagerAgent
            "temperature": None,
            "max_tokens": None,
            "thinking": None,
            "rules_file": self.MANAGER_RULES_FILE,  # Add rules_file reference
        }
        
        # Apply temperature override if set
        if self.MANAGER_TEMP_OVERRIDE:
            try:
                config["temperature"] = float(self.MANAGER_TEMP_OVERRIDE)
            except ValueError:
                pass
        
        # Apply tokens override if set
        if self.MANAGER_TOKENS_OVERRIDE:
            try:
                config["max_tokens"] = int(self.MANAGER_TOKENS_OVERRIDE)
            except ValueError:
                pass
        
        # Load rules file if specified
        if config.get("rules_file"):
            rules_path = _PROJECT_ROOT / "src/core/manager_profiles" / config["rules_file"]
            if rules_path.exists():
                try:
                    with open(rules_path, "r", encoding="utf-8") as f:
                        config["rules"] = yaml.safe_load(f)
                except Exception as e:
                    logger.warning(f"Failed to load manager rules '{config['rules_file']}': {e}")
        
        return config

    def get_orchestrator_config(self) -> dict[str, Any]:
        """Get configuration for the Orchestrator LLM calls (legacy alias for get_manager_config)."""
        return self.get_manager_config()

    def validate_config(self) -> list[dict[str, str]]:
        """
        Validate configuration and return a list of issues.
        Each issue is a dict with 'level' ('error'|'warning') and 'message'.
        """
        issues: list[dict[str, str]] = []

        # Check .env file exists
        env_path = _ENV_FILE
        if not env_path.exists():
            issues.append({
                "level": "warning",
                "message": ".env file not found. Using default values. Copy .env.example to .env",
            })

        # Check agent path
        agent_path = self.agent_path_resolved
        if not agent_path.exists():
            issues.append({
                "level": "error",
                "message": f"AGENT_PATH does not exist: {agent_path}",
            })
        elif not (agent_path / "pyproject.toml").exists():
            issues.append({
                "level": "warning",
                "message": f"AGENT_PATH may be invalid (no pyproject.toml found): {agent_path}",
            })

        # Check API keys are not dummy defaults
        if self.ORCHESTRATOR_API_KEY == "sk-dummy-orchestrator-key":
            issues.append({
                "level": "warning",
                "message": "ORCHESTRATOR_API_KEY is set to default dummy value",
            })

        # Check API base URL format
        for name, url in [
            ("ORCHESTRATOR_API_BASE", self.ORCHESTRATOR_API_BASE),
            ("PROXY_URL", self.PROXY_URL),
        ]:
            if not url.startswith(("http://", "https://")):
                issues.append({
                    "level": "error",
                    "message": f"{name} has invalid URL format: {url}",
                })

        # Check timeout value
        if self.WORKER_TIMEOUT < 0:
            issues.append({
                "level": "error",
                "message": f"WORKER_TIMEOUT cannot be negative: {self.WORKER_TIMEOUT}",
            })

        # Check MAX_WORKER_ITERATIONS
        if self.MAX_WORKER_ITERATIONS < 1:
            issues.append({
                "level": "error",
                "message": f"MAX_WORKER_ITERATIONS must be >= 1: {self.MAX_WORKER_ITERATIONS}",
            })

        return issues


_settings_instance: Settings | None = None
_settings_lock = threading.Lock()


def get_settings() -> Settings:
    """Get the global settings singleton.

    Uses an explicit module-level singleton instead of lru_cache so that
    reload_settings() updates the same object in-place, keeping all existing
    references valid.
    """
    global _settings_instance
    if _settings_instance is None:
        with _settings_lock:
            if _settings_instance is None:
                _settings_instance = Settings()
    return _settings_instance


def reload_settings(*, clear_overrides: bool = False) -> Settings:
    """Reload settings from .env file, updating the existing singleton in-place.

    Unlike the previous lru_cache approach, this mutates the existing Settings
    object so that all code holding a reference to it sees the updated values.
    Thread-safe: all field updates are done under a lock.

    Args:
        clear_overrides: If True, clear all runtime overrides (e.g. on /system reload).
                         If False (default), preserve session overrides set via /manager commands.
    """
    global _settings_instance
    fresh = Settings()
    with _settings_lock:
        if _settings_instance is None:
            _settings_instance = fresh
        else:
            _OVERRIDE_FIELDS = (
                "MANAGER_MODEL_OVERRIDE", "MANAGER_API_BASE_OVERRIDE",
                "MANAGER_API_KEY_OVERRIDE", "MANAGER_TEMP_OVERRIDE",
                "MANAGER_TOKENS_OVERRIDE",
            )
            # Save current overrides before refreshing fields
            saved: dict[str, str] = {}
            if not clear_overrides:
                for f in _OVERRIDE_FIELDS:
                    saved[f] = getattr(_settings_instance, f, "")

            # Update existing instance in-place so all references stay valid
            for field_name in Settings.model_fields:
                setattr(_settings_instance, field_name, getattr(fresh, field_name))

            # Restore or clear runtime overrides
            if not clear_overrides:
                for f, v in saved.items():
                    setattr(_settings_instance, f, v)
            else:
                for f in _OVERRIDE_FIELDS:
                    setattr(_settings_instance, f, "")
    return _settings_instance


def write_env_value(key: str, value: str):
    """Update a KEY=value line in the .env file, preserving comments. Adds if not found."""
    ALLOWED_KEYS = {
        "ORCHESTRATOR_MODEL", "ORCHESTRATOR_API_BASE", "ORCHESTRATOR_API_KEY",
        "WORKER_MODEL", "WORKER_PROFILE", "MANAGER_PROFILE",
        "PROXY_URL", "PROXY_KEY", "AGENT_PATH",
        "VERBOSE_WORKER", "MAX_WORKER_ITERATIONS", "WORKER_TIMEOUT",
    }
    if key not in ALLOWED_KEYS:
        raise ValueError(f"Unknown config key: {key}")
    value = value.replace("\n", "").replace("\r", "")
    if not _ENV_FILE.exists():
        _ENV_FILE.write_text(f"{key}={value}\n", encoding="utf-8")
        return

    lines = _ENV_FILE.read_text(encoding="utf-8").splitlines()
    found = False
    for i, line in enumerate(lines):
        # Skip pure comment lines
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # Check if this line sets the key
        # Use regex to find inline comments: unquoted # preceded by whitespace
        import re
        match = re.match(rf'^{re.escape(key)}=', line)
        if match:
            # Find inline comment: # preceded by at least one space, not inside the value
            # We look for ' #' or '\t#' pattern after the value to identify comments
            raw_after_key = line[len(key) + 1:]  # everything after KEY=
            comment = ""
            # Only treat # as comment if preceded by whitespace (not part of value)
            comment_match = re.search(r'\s+#\s', raw_after_key)
            if comment_match:
                comment = "  " + raw_after_key[comment_match.start():].lstrip()
            lines[i] = f"{key}={value}{comment}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    tmp_path = _ENV_FILE.with_suffix(".tmp")
    tmp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    import os
    os.replace(str(tmp_path), str(_ENV_FILE))


# ================================================================
# Shared ThreadPoolExecutor
# ================================================================

_shared_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()


def get_executor(max_workers: int = 12) -> ThreadPoolExecutor:
    """Get the shared ThreadPoolExecutor singleton.

    All modules (manager, sub_manager, llm_pool) should use this
    instead of creating their own executors.
    """
    global _shared_executor
    if _shared_executor is None:
        with _executor_lock:
            if _shared_executor is None:
                _shared_executor = ThreadPoolExecutor(max_workers=max_workers)
    return _shared_executor


def _shutdown_executor():
    global _shared_executor
    if _shared_executor is not None:
        _shared_executor.shutdown(wait=False)
        _shared_executor = None


atexit.register(_shutdown_executor)

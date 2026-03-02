"""Tests for the configuration module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from src.core.config import Settings


class TestSettings:
    """Tests for Settings class."""

    def test_default_values(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(
                _env_file=None,
                ORCHESTRATOR_API_KEY="test-key",
                PROXY_KEY="test-proxy",

            )
            assert settings.ORCHESTRATOR_MODEL == "claude-3-5-sonnet-20241022"
            assert settings.VERBOSE_WORKER is False
            assert settings.MAX_WORKER_ITERATIONS == 5
            assert settings.WORKER_PROFILE == "livesweagent"

    def test_agent_path_resolved_absolute(self):
        settings = Settings(
            _env_file=None,
            AGENT_PATH="/absolute/path",
            ORCHESTRATOR_API_KEY="test",
            PROXY_KEY="test",

        )
        result = settings.agent_path_resolved
        assert result.is_absolute()

    def test_agent_path_resolved_relative(self):
        settings = Settings(
            _env_file=None,
            AGENT_PATH="../relative",
            ORCHESTRATOR_API_KEY="test",
            PROXY_KEY="test",
        )
        result = settings.agent_path_resolved
        assert result.is_absolute()

    def test_get_agent_env(self):
        settings = Settings(
            _env_file=None,
            PROXY_URL="http://test:8045",
            PROXY_KEY="sk-proxy",
            ORCHESTRATOR_API_KEY="test",
        )
        env = settings.get_agent_env()
        assert env["MINI_API_BASE"] == "http://test:8045"
        assert env["MINI_API_KEY"] == "sk-proxy"
        assert len(env) == 2  # Only MINI_API_BASE and MINI_API_KEY

    def test_get_orchestrator_config(self):
        settings = Settings(
            _env_file=None,
            MANAGER_PROFILE="",  # Empty to force ORCHESTRATOR_* fallback
            ORCHESTRATOR_MODEL="test-model",
            ORCHESTRATOR_API_BASE="http://test:9000",
            ORCHESTRATOR_API_KEY="sk-orch",
            PROXY_KEY="test",

        )
        config = settings.get_orchestrator_config()
        assert config["model"] == "test-model"
        assert config["api_base"] == "http://test:9000"
        assert config["api_key"] == "sk-orch"

    # ================================================================
    # Config validation tests
    # ================================================================

    def test_validate_config_no_issues(self, tmp_path):
        agent_path = tmp_path / "agent"
        agent_path.mkdir()
        (agent_path / "pyproject.toml").write_text("[project]", encoding="utf-8")

        settings = Settings(
            _env_file=None,
            ORCHESTRATOR_API_KEY="sk-real-key",
            ORCHESTRATOR_API_BASE="http://localhost:8045",
            PROXY_URL="http://localhost:8045",
            PROXY_KEY="test",

            AGENT_PATH=str(agent_path),
        )
        issues = settings.validate_config()
        # Only .env warning expected (no .env file in test)
        error_issues = [i for i in issues if i["level"] == "error"]
        assert len(error_issues) == 0

    def test_validate_config_invalid_agent_path(self):
        settings = Settings(
            _env_file=None,
            ORCHESTRATOR_API_KEY="test",
            PROXY_KEY="test",

            AGENT_PATH="/nonexistent/path/to/agent",
        )
        issues = settings.validate_config()
        error_msgs = [i["message"] for i in issues if i["level"] == "error"]
        assert any("AGENT_PATH" in m for m in error_msgs)

    def test_validate_config_invalid_url(self):
        settings = Settings(
            _env_file=None,
            ORCHESTRATOR_API_KEY="test",
            ORCHESTRATOR_API_BASE="not-a-url",
            PROXY_URL="http://valid:8045",
            PROXY_KEY="test",

        )
        issues = settings.validate_config()
        error_msgs = [i["message"] for i in issues if i["level"] == "error"]
        assert any("ORCHESTRATOR_API_BASE" in m for m in error_msgs)

    def test_validate_config_negative_timeout(self):
        settings = Settings(
            _env_file=None,
            ORCHESTRATOR_API_KEY="test",
            PROXY_KEY="test",

            WORKER_TIMEOUT=-1,
        )
        issues = settings.validate_config()
        error_msgs = [i["message"] for i in issues if i["level"] == "error"]
        assert any("WORKER_TIMEOUT" in m for m in error_msgs)

    def test_validate_config_dummy_api_key_warning(self):
        settings = Settings(
            _env_file=None,
            ORCHESTRATOR_API_KEY="sk-dummy-orchestrator-key",
            PROXY_KEY="test",

        )
        issues = settings.validate_config()
        warning_msgs = [i["message"] for i in issues if i["level"] == "warning"]
        assert any("ORCHESTRATOR_API_KEY" in m for m in warning_msgs)

    # ================================================================
    # write_env_value tests
    # ================================================================

    def test_write_env_value_update_existing(self, tmp_path):
        from src.core import config as cfg
        env_file = tmp_path / ".env"
        env_file.write_text("ORCHESTRATOR_MODEL=old_value\nPROXY_URL=http://keep\n", encoding="utf-8")
        original = cfg._ENV_FILE
        cfg._ENV_FILE = env_file
        try:
            cfg.write_env_value("ORCHESTRATOR_MODEL", "new_value")
            content = env_file.read_text(encoding="utf-8")
            assert "ORCHESTRATOR_MODEL=new_value" in content
            assert "PROXY_URL=http://keep" in content
        finally:
            cfg._ENV_FILE = original

    def test_write_env_value_preserves_comment(self, tmp_path):
        from src.core import config as cfg
        env_file = tmp_path / ".env"
        env_file.write_text("ORCHESTRATOR_MODEL=old  # My model\n", encoding="utf-8")
        original = cfg._ENV_FILE
        cfg._ENV_FILE = env_file
        try:
            cfg.write_env_value("ORCHESTRATOR_MODEL", "new")
            content = env_file.read_text(encoding="utf-8")
            assert "ORCHESTRATOR_MODEL=new" in content
            assert "# My model" in content
        finally:
            cfg._ENV_FILE = original

    def test_write_env_value_adds_new_key(self, tmp_path):
        from src.core import config as cfg
        env_file = tmp_path / ".env"
        env_file.write_text("ORCHESTRATOR_MODEL=yes\n", encoding="utf-8")
        original = cfg._ENV_FILE
        cfg._ENV_FILE = env_file
        try:
            cfg.write_env_value("WORKER_MODEL", "hello")
            content = env_file.read_text(encoding="utf-8")
            assert "ORCHESTRATOR_MODEL=yes" in content
            assert "WORKER_MODEL=hello" in content
        finally:
            cfg._ENV_FILE = original


class TestProviderDetection:
    """Tests for detect_provider and strip_provider_prefix."""

    def test_detect_claude_models(self):
        from src.core.config import detect_provider
        assert detect_provider("claude-opus-4-6-thinking") == "anthropic"
        assert detect_provider("claude-3-5-sonnet-20241022") == "anthropic"
        assert detect_provider("claude-3-haiku") == "anthropic"

    def test_detect_openai_models(self):
        from src.core.config import detect_provider
        assert detect_provider("gpt-4o") == "openai"
        assert detect_provider("gpt-4-turbo") == "openai"
        assert detect_provider("o1-mini") == "openai"

    def test_detect_gemini_models(self):
        from src.core.config import detect_provider
        assert detect_provider("gemini-pro") == "google"
        assert detect_provider("gemini-1.5-flash") == "google"

    def test_detect_explicit_prefix(self):
        from src.core.config import detect_provider
        assert detect_provider("anthropic/claude-opus-4") == "anthropic"
        assert detect_provider("openai/gpt-4o") == "openai"

    def test_strip_provider_prefix(self):
        from src.core.config import strip_provider_prefix
        assert strip_provider_prefix("anthropic/claude-opus-4") == "claude-opus-4"
        assert strip_provider_prefix("openai/gpt-4o") == "gpt-4o"
        assert strip_provider_prefix("gpt-4o") == "gpt-4o"

    def test_get_agent_env_simplified(self):
        settings = Settings(
            _env_file=None,
            PROXY_URL="http://localhost:8045",
            PROXY_KEY="sk-test",
            ORCHESTRATOR_API_KEY="test",
        )
        env = settings.get_agent_env()
        assert env == {"MINI_API_BASE": "http://localhost:8045", "MINI_API_KEY": "sk-test"}
        assert "ANTHROPIC_API_KEY" not in env
        assert "OPENAI_API_KEY" not in env
        assert "LITELLM_API_KEY" not in env

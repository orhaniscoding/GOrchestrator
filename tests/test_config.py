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
                BYPASS_KEY="test-bypass",
            )
            assert settings.ORCHESTRATOR_MODEL == "claude-3-5-sonnet-20241022"
            assert settings.VERBOSE_WORKER is False
            assert settings.MAX_WORKER_ITERATIONS == 5
            assert settings.WORKER_PROFILE == "live"

    def test_agent_path_resolved_absolute(self):
        settings = Settings(
            _env_file=None,
            AGENT_PATH="/absolute/path",
            ORCHESTRATOR_API_KEY="test",
            PROXY_KEY="test",
            BYPASS_KEY="test",
        )
        result = settings.agent_path_resolved
        assert result.is_absolute()

    def test_agent_path_resolved_relative(self):
        settings = Settings(
            _env_file=None,
            AGENT_PATH="../relative",
            ORCHESTRATOR_API_KEY="test",
            PROXY_KEY="test",
            BYPASS_KEY="test",
        )
        result = settings.agent_path_resolved
        assert result.is_absolute()

    def test_get_agent_env(self):
        settings = Settings(
            _env_file=None,
            PROXY_URL="http://test:8045",
            BYPASS_KEY="sk-test",
            PROXY_KEY="sk-proxy",
            ORCHESTRATOR_API_KEY="test",
        )
        env = settings.get_agent_env()
        assert env["MINI_API_BASE"] == "http://test:8045"
        assert env["ANTHROPIC_API_KEY"] == "sk-test"
        assert env["OPENAI_API_KEY"] == "sk-test"
        assert env["LITELLM_API_KEY"] == "sk-proxy"

    def test_get_orchestrator_config(self):
        settings = Settings(
            _env_file=None,
            ORCHESTRATOR_MODEL="test-model",
            ORCHESTRATOR_API_BASE="http://test:9000",
            ORCHESTRATOR_API_KEY="sk-orch",
            PROXY_KEY="test",
            BYPASS_KEY="test",
        )
        config = settings.get_orchestrator_config()
        assert config["model"] == "test-model"
        assert config["api_base"] == "http://test:9000"
        assert config["api_key"] == "sk-orch"

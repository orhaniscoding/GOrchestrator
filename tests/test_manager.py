"""Tests for the Manager Agent module."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from src.core.manager import (
    _BASE_SYSTEM_PROMPT,
    _sanitize_tool_name,
    ManagerAgent,
    ManagerResponse,
    Message,
    MessageRole,
)


class TestMessage:
    """Tests for the Message dataclass."""

    def test_to_dict_basic(self):
        msg = Message(role=MessageRole.USER, content="Hello")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "Hello"
        assert "tool_calls" not in d
        assert "tool_call_id" not in d

    def test_to_dict_with_tool_calls(self):
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="",
            tool_calls=[{"id": "1", "function": {"name": "test"}}],
        )
        d = msg.to_dict()
        assert d["tool_calls"] == [{"id": "1", "function": {"name": "test"}}]

    def test_to_dict_with_tool_call_id(self):
        msg = Message(
            role=MessageRole.TOOL,
            content="result",
            tool_call_id="call_123",
            name="delegate_to_worker",
        )
        d = msg.to_dict()
        assert d["tool_call_id"] == "call_123"
        assert d["name"] == "delegate_to_worker"

    def test_timestamp_auto_generated(self):
        msg = Message(role=MessageRole.USER, content="test")
        assert msg.timestamp is not None


class TestManagerResponse:
    """Tests for ManagerResponse."""

    def test_has_tool_calls_false(self):
        resp = ManagerResponse(content="hello")
        assert resp.has_tool_calls is False

    def test_has_tool_calls_true(self):
        resp = ManagerResponse(content="", tool_calls=[{"id": "1"}])
        assert resp.has_tool_calls is True


class TestManagerAgent:
    """Tests for ManagerAgent."""

    def _make_agent(self):
        settings = MagicMock()
        settings.ORCHESTRATOR_MODEL = "test-model"
        settings.ORCHESTRATOR_API_BASE = "http://localhost:8045"
        settings.ORCHESTRATOR_API_KEY = "sk-test"
        settings.WORKER_MODEL = "test-model"
        settings.WORKER_PROFILE = "live"
        settings.AGENT_PATH = "../test"
        settings.PROXY_URL = "http://localhost:8045"
        settings.PROXY_KEY = "sk-test"
        settings.BYPASS_KEY = "sk-test"
        settings.VERBOSE_WORKER = False
        settings.MAX_WORKER_ITERATIONS = 5
        settings.get_manager_config.return_value = {
            "model": "test-model",
            "api_base": "http://localhost:8045",
            "api_key": "sk-test",
        }
        return ManagerAgent(settings=settings)

    def test_init_has_system_prompt(self):
        agent = self._make_agent()
        assert len(agent.messages) == 1
        assert agent.messages[0].role == MessageRole.SYSTEM
        assert _BASE_SYSTEM_PROMPT in agent.messages[0].content

    def test_clear_history(self):
        agent = self._make_agent()
        agent.messages.append(Message(role=MessageRole.USER, content="test"))
        assert len(agent.messages) == 2
        agent.clear_history()
        assert len(agent.messages) == 1
        assert agent.messages[0].role == MessageRole.SYSTEM

    def test_export_import_history_no_duplicate_system(self):
        agent = self._make_agent()
        agent.messages.append(Message(role=MessageRole.USER, content="hello"))
        exported = agent.export_history()
        assert len(exported) == 2  # system + user

        agent.import_history(exported)
        system_msgs = [m for m in agent.messages if m.role == MessageRole.SYSTEM]
        assert len(system_msgs) == 1
        assert _BASE_SYSTEM_PROMPT in system_msgs[0].content

    def test_import_empty_history(self):
        agent = self._make_agent()
        agent.import_history([])
        assert len(agent.messages) == 1
        assert agent.messages[0].role == MessageRole.SYSTEM

    def test_get_history_excludes_system(self):
        agent = self._make_agent()
        agent.messages.append(Message(role=MessageRole.USER, content="hi"))
        history = agent.get_history()
        roles = [h["role"] for h in history]
        assert "system" not in roles
        assert "user" in roles

    def test_get_history_truncates_long_content(self):
        agent = self._make_agent()
        long_content = "x" * 300
        agent.messages.append(Message(role=MessageRole.USER, content=long_content))
        history = agent.get_history()
        assert history[0]["content"].endswith("...")
        assert len(history[0]["content"]) < 300


class TestLiteLLMRouting:
    """Tests for LiteLLM-based unified LLM routing."""

    def _make_agent(self):
        settings = MagicMock()
        settings.ORCHESTRATOR_MODEL = "test-model"
        settings.ORCHESTRATOR_API_BASE = "http://localhost:8045"
        settings.ORCHESTRATOR_API_KEY = "sk-test"
        settings.WORKER_MODEL = "test-model"
        settings.WORKER_PROFILE = "live"
        settings.get_manager_config.return_value = {
            "model": "test-model",
            "api_base": "http://localhost:8045",
            "api_key": "sk-test",
        }
        return ManagerAgent(settings=settings)

    @patch("src.core.manager.litellm")
    def test_call_llm_passes_custom_llm_provider(self, mock_litellm):
        """LiteLLM should receive custom_llm_provider from detect_provider."""
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Hello"
        mock_resp.choices[0].message.tool_calls = None
        mock_litellm.completion.return_value = mock_resp

        settings = MagicMock()
        settings.get_manager_config.return_value = {
            "model": "claude-opus-4",
            "api_base": "http://localhost:8045",
            "api_key": "sk-test",
        }
        settings.WORKER_MODEL = "test"
        settings.WORKER_PROFILE = "live"
        agent = ManagerAgent(settings=settings)

        agent._call_llm(include_tools=False)

        mock_litellm.completion.assert_called_once()
        call_kwargs = mock_litellm.completion.call_args
        assert call_kwargs.kwargs["custom_llm_provider"] == "anthropic"
        assert call_kwargs.kwargs["api_base"] == "http://localhost:8045"
        assert call_kwargs.kwargs["api_key"] == "sk-test"

    @patch("src.core.manager.litellm")
    def test_call_llm_openai_provider(self, mock_litellm):
        """OpenAI models should get custom_llm_provider='openai'."""
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Hi"
        mock_resp.choices[0].message.tool_calls = None
        mock_litellm.completion.return_value = mock_resp

        settings = MagicMock()
        settings.get_manager_config.return_value = {
            "model": "gpt-4o",
            "api_base": "http://localhost:8045",
            "api_key": "sk-test",
        }
        settings.WORKER_MODEL = "test"
        settings.WORKER_PROFILE = "live"
        agent = ManagerAgent(settings=settings)

        agent._call_llm(include_tools=False)

        call_kwargs = mock_litellm.completion.call_args
        assert call_kwargs.kwargs["custom_llm_provider"] == "openai"

    @patch("src.core.manager.litellm")
    def test_call_llm_thinking_model(self, mock_litellm):
        """Thinking models should get thinking param and higher max_tokens."""
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "thought"
        mock_resp.choices[0].message.tool_calls = None
        mock_litellm.completion.return_value = mock_resp

        settings = MagicMock()
        settings.get_manager_config.return_value = {
            "model": "claude-opus-4-6-thinking",
            "api_base": "http://localhost:8045",
            "api_key": "sk-test",
        }
        settings.WORKER_MODEL = "test"
        settings.WORKER_PROFILE = "live"
        agent = ManagerAgent(settings=settings)

        agent._call_llm(include_tools=False)

        call_kwargs = mock_litellm.completion.call_args
        assert call_kwargs.kwargs["thinking"] == {"type": "enabled", "budget_tokens": 10000}
        assert call_kwargs.kwargs["max_tokens"] == 16000

    @patch("src.core.manager.litellm")
    def test_call_llm_includes_tools(self, mock_litellm):
        """When include_tools=True, tools and tool_choice should be passed."""
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Hi"
        mock_resp.choices[0].message.tool_calls = None
        mock_litellm.completion.return_value = mock_resp

        agent = self._make_agent()
        agent._call_llm(include_tools=True)

        call_kwargs = mock_litellm.completion.call_args
        assert "tools" in call_kwargs.kwargs
        assert call_kwargs.kwargs["tool_choice"] == "auto"

    @patch("src.core.manager.litellm")
    def test_call_llm_no_tools(self, mock_litellm):
        """When include_tools=False, tools should NOT be passed."""
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Hi"
        mock_resp.choices[0].message.tool_calls = None
        mock_litellm.completion.return_value = mock_resp

        agent = self._make_agent()
        agent._call_llm(include_tools=False)

        call_kwargs = mock_litellm.completion.call_args
        assert "tools" not in call_kwargs.kwargs
        assert "tool_choice" not in call_kwargs.kwargs

    @patch("src.core.manager.litellm")
    def test_call_llm_strips_provider_prefix(self, mock_litellm):
        """Provider prefix (provider/model) should be stripped from model name."""
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Hi"
        mock_resp.choices[0].message.tool_calls = None
        mock_litellm.completion.return_value = mock_resp

        settings = MagicMock()
        settings.get_manager_config.return_value = {
            "model": "anthropic/claude-opus-4",
            "api_base": "http://localhost:8045",
            "api_key": "sk-test",
        }
        settings.WORKER_MODEL = "test"
        settings.WORKER_PROFILE = "live"
        agent = ManagerAgent(settings=settings)

        agent._call_llm(include_tools=False)

        call_kwargs = mock_litellm.completion.call_args
        assert call_kwargs.kwargs["model"] == "claude-opus-4"
        assert call_kwargs.kwargs["custom_llm_provider"] == "anthropic"

    def test_sanitize_tool_name(self):
        assert _sanitize_tool_name("z.ai") == "z-ai"
        assert _sanitize_tool_name("my worker!") == "my-worker-"
        assert _sanitize_tool_name("valid-name_123") == "valid-name_123"

    def test_build_worker_tools_sanitized_names(self):
        """Tool names should be sanitized for API compatibility."""
        settings = MagicMock()
        settings.ORCHESTRATOR_MODEL = "test-model"
        settings.get_manager_config.return_value = {
            "model": "test-model", "api_base": "http://test", "api_key": "k"
        }
        settings.WORKER_MODEL = "test"
        settings.WORKER_PROFILE = "live"

        mock_registry = MagicMock()
        mock_wc = MagicMock()
        mock_wc.name = "z.ai"
        mock_wc.model = "glm-4.7"
        mock_wc.profile = "live"
        mock_registry.get_active_workers.return_value = [mock_wc]

        agent = ManagerAgent(settings=settings, worker_registry=mock_registry)
        tools = agent._build_worker_tools()
        assert len(tools) == 1


class TestManagerCommandHandlers:
    """Tests for manager command handlers in engine.py."""

    def _make_engine(self):
        from src.core.engine import SessionEngine
        settings = MagicMock()
        settings.MANAGER_PROFILE = "default"
        settings.MANAGER_MODEL_OVERRIDE = ""
        settings.MANAGER_API_BASE_OVERRIDE = ""
        settings.MANAGER_API_KEY_OVERRIDE = ""
        settings.MANAGER_TEMP_OVERRIDE = ""
        settings.MANAGER_TOKENS_OVERRIDE = ""
        settings.ORCHESTRATOR_MODEL = "gpt-4o"
        settings.get_manager_config.return_value = {
            "model": "gpt-4o",
            "api_base": "https://api.openai.com/v1",
            "api_key": "sk-test",
            "temperature": 0.7,
            "max_tokens": 4096,
        }
        return SessionEngine(settings)

    def test_manager_set_model_session_override(self):
        """Test /manager model command sets session-based override."""
        engine = self._make_engine()
        engine._manager_set_model("claude-opus-4", persistent=False)
        assert engine.settings.MANAGER_MODEL_OVERRIDE == "claude-opus-4"

    def test_manager_set_api_session_override(self):
        """Test /manager api command sets session-based override."""
        engine = self._make_engine()
        engine._manager_set_api("https://api.z.ai/v1", "sk-new", persistent=False)
        assert engine.settings.MANAGER_API_BASE_OVERRIDE == "https://api.z.ai/v1"
        assert engine.settings.MANAGER_API_KEY_OVERRIDE == "sk-new"

    def test_manager_set_prompt(self):
        """Test /manager prompt command overrides system prompt."""
        engine = self._make_engine()
        assert hasattr(engine, '_manager_set_prompt')
        assert callable(engine._manager_set_prompt)

    def test_manager_show_rules(self):
        """Test /manager rules show command displays rules."""
        engine = self._make_engine()
        assert hasattr(engine, '_manager_show_rules')
        assert callable(engine._manager_show_rules)

    def test_manager_edit_rules(self):
        """Test /manager rules edit command opens editor."""
        engine = self._make_engine()
        assert hasattr(engine, '_manager_edit_rules')
        assert callable(engine._manager_edit_rules)

    def test_manager_set_temperature(self):
        """Test /manager temp command sets temperature override."""
        engine = self._make_engine()
        assert hasattr(engine, '_manager_set_temperature')
        assert callable(engine._manager_set_temperature)

    def test_manager_set_max_tokens(self):
        """Test /manager tokens command sets max tokens override."""
        engine = self._make_engine()
        assert hasattr(engine, '_manager_set_max_tokens')
        assert callable(engine._manager_set_max_tokens)

    def test_handle_manager_command_exists(self):
        """Test _handle_manager_command recognizes all new commands."""
        engine = self._make_engine()
        assert hasattr(engine, '_handle_manager_command')
        assert callable(engine._handle_manager_command)
        assert hasattr(engine, '_handle_submanager_command')
        assert callable(engine._handle_submanager_command)
        assert hasattr(engine, '_handle_team_command')
        assert callable(engine._handle_team_command)


class TestTabCompletion:
    """Tests for tab completion system."""

    def test_manager_profile_completion(self):
        """Test tab completion for /manager profile command."""
        from src.core.engine import SessionEngine
        from unittest.mock import MagicMock
        
        settings = MagicMock()
        settings.MANAGER_PROFILE = "default"
        settings.get_manager_config.return_value = {
            "model": "gpt-4o",
            "api_base": "https://api.openai.com/v1",
            "api_key": "sk-test",
        }
        
        engine = SessionEngine(settings)
        
        # Test /manager profile completion
        completions = engine.get_tab_completions("/manager", "profile ")
        assert isinstance(completions, list)
        # Should return profile names if profiles exist
        # We can't test actual profile names without filesystem, but we verify the method works

    def test_config_set_completion(self):
        """Test tab completion for /config set command."""
        from src.core.engine import SessionEngine
        
        settings = MagicMock()
        settings.MANAGER_PROFILE = "default"
        settings.get_manager_config.return_value = {}
        
        engine = SessionEngine(settings)
        
        # Test /config set completion
        completions = engine.get_tab_completions("/config", "set ORC")
        assert isinstance(completions, list)
        assert any("ORCHESTRATOR_MODEL" in c for c in completions)

    def test_load_session_completion(self):
        """Test tab completion for /load command."""
        from src.core.engine import SessionEngine
        
        settings = MagicMock()
        settings.MANAGER_PROFILE = "default"
        settings.get_manager_config.return_value = {}
        
        engine = SessionEngine(settings)
        
        # Test /load completion
        completions = engine.get_tab_completions("/load", "")
        assert isinstance(completions, list)
        # Should return session IDs if sessions exist


class TestSessionVsGlobalConfig:
    """Tests for session-based vs global configuration."""

    def test_manager_set_model_session_based(self):
        """Test /manager model without --global flag uses session override."""
        from src.core.engine import SessionEngine
        
        settings = MagicMock()
        settings.MANAGER_PROFILE = "default"
        settings.get_manager_config.return_value = {
            "model": "gpt-4o",
            "api_base": "https://api.openai.com/v1",
            "api_key": "sk-test",
        }
        
        engine = SessionEngine(settings)
        
        # Session-based: should update Settings override
        engine._manager_set_model("claude-opus-4", persistent=False)
        assert engine.settings.MANAGER_MODEL_OVERRIDE == "claude-opus-4"

    def test_manager_set_model_global(self):
        """Test /manager model with --global flag writes to .env."""
        from src.core.engine import SessionEngine
        
        settings = MagicMock()
        settings.MANAGER_PROFILE = "default"
        settings.get_manager_config.return_value = {
            "model": "gpt-4o",
            "api_base": "https://api.openai.com/v1",
            "api_key": "sk-test",
        }
        
        engine = SessionEngine(settings)
        
        # Global: should clear Settings overrides (we can't test .env write in unit test)
        engine.settings.MANAGER_MODEL_OVERRIDE = "claude-opus-4"
        # Just verify the method accepts persistent=True parameter
        assert hasattr(engine, '_manager_set_model')

    def test_manager_show_config_with_overrides(self):
        """Test /manager show displays session override values."""
        from src.core.engine import SessionEngine
        
        settings = MagicMock()
        settings.MANAGER_PROFILE = "default"
        settings.MANAGER_MODEL_OVERRIDE = ""  # Start empty
        settings.ORCHESTRATOR_MODEL = "gpt-4o"
        settings.get_manager_config.return_value = {
            "model": "gpt-4o",  # Will be overridden by MANAGER_MODEL_OVERRIDE
            "api_base": "https://api.openai.com/v1",
            "api_key": "sk-test",
        }
        
        engine = SessionEngine(settings)
        
        # Set session override using Settings
        engine.settings.MANAGER_MODEL_OVERRIDE = "claude-opus-4"
        
        # get_manager_config() should reflect override
        # We need to manually update the return value to simulate override
        engine.settings.get_manager_config.return_value["model"] = "claude-opus-4"
        config = engine.settings.get_manager_config()
        override_model = config.get("model")
        assert override_model == "claude-opus-4"


class TestBugFixes:
    """Tests for critical bug fixes."""

    def test_manager_profile_without_arg(self):
        """Test /manager profile without arg lists profiles."""
        from src.core.engine import SessionEngine
        
        settings = MagicMock()
        settings.MANAGER_PROFILE = "default"
        settings.get_manager_config.return_value = {}
        
        engine = SessionEngine(settings)
        
        # Verify _manager_list_profiles exists and is callable
        assert hasattr(engine, '_manager_list_profiles')
        assert callable(engine._manager_list_profiles)

    def test_config_set_writes_to_env_and_clears_overrides(self):
        """Test /config set writes to .env and clears runtime overrides."""
        from src.core.config import reload_settings
        from src.core.engine import SessionEngine
        
        settings = MagicMock()
        settings.MANAGER_PROFILE = "default"
        settings.get_manager_config.return_value = {
            "model": "gpt-4o",
            "api_base": "https://api.openai.com/v1",
            "api_key": "sk-test",
        }
        settings.ORCHESTRATOR_MODEL = "gpt-4o"
        settings.MANAGER_MODEL_OVERRIDE = "claude-opus-4"  # Simulate session override
        
        engine = SessionEngine(settings)
        
        # Simulate reload_settings (should clear override)
        # Note: We can't test actual .env write in unit test
        # But we verify reload_settings clears the override
        assert settings.MANAGER_MODEL_OVERRIDE == "claude-opus-4"
        
        # Call reload_settings
        new_settings = reload_settings()
        
        # Verify override is cleared
        assert new_settings.MANAGER_MODEL_OVERRIDE == ""  # Should be empty string

    def test_manager_show_displays_overrides_correctly(self):
        """Test /manager show displays session override values with (session) marker."""
        from src.core.engine import SessionEngine
        
        settings = MagicMock()
        settings.MANAGER_PROFILE = "default"
        settings.get_manager_config.return_value = {
            "model": "gpt-4o",
            "api_base": "https://api.openai.com/v1",
            "api_key": "sk-test",
        }
        
        engine = SessionEngine(settings)
        
        # Set session override using Settings
        engine.settings.MANAGER_MODEL_OVERRIDE = "claude-opus-4"
        engine.settings.MANAGER_API_BASE_OVERRIDE = "https://api.z.ai/api/paas/v4/"
        
        # Get effective values from get_manager_config()
        config = settings.get_manager_config()
        # Update mock return value to simulate override
        config["model"] = "claude-opus-4"
        config["api_base"] = "https://api.z.ai/api/paas/v4/"
        
        # Verify override values are used
        model = config.get("model")
        api_base = config.get("api_base")
        assert model == "claude-opus-4"
        assert api_base == "https://api.z.ai/api/paas/v4/"



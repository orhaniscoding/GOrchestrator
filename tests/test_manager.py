"""Tests for the Manager Agent module."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from src.core.manager import (
    MANAGER_SYSTEM_PROMPT,
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
        settings.get_orchestrator_config.return_value = {
            "model": "test-model",
            "api_base": "http://localhost:8045",
            "api_key": "sk-test",
        }
        return ManagerAgent(settings=settings)

    def test_init_has_system_prompt(self):
        agent = self._make_agent()
        assert len(agent.messages) == 1
        assert agent.messages[0].role == MessageRole.SYSTEM
        assert agent.messages[0].content == MANAGER_SYSTEM_PROMPT

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
        assert system_msgs[0].content == MANAGER_SYSTEM_PROMPT

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

"""Tests for the Session Engine module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from src.core.engine import SessionEngine, SessionMode


class TestSessionEngine:
    """Tests for SessionEngine."""

    def _make_engine(self, tmp_path):
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
        settings.agent_path_resolved = Path("../test")

        engine = SessionEngine(settings=settings)
        engine.SESSIONS_DIR = tmp_path / "sessions"
        engine._ensure_sessions_dir()
        return engine

    def test_save_and_load_session(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._init_manager()

        path = engine.save_session("test_session")
        assert path.exists()

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["version"] == "2.0"
        assert "manager_history" in data

    def test_list_sessions(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._init_manager()

        engine.save_session("session_a")
        engine.save_session("session_b")

        sessions = engine.list_sessions()
        assert "session_a" in sessions
        assert "session_b" in sessions

    def test_load_nonexistent_session(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine.load_session("does_not_exist")
        assert result is False

    def test_handle_slash_command_help(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/help")
        assert result is True

    def test_handle_slash_command_verbose(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/verbose")
        assert result is True
        assert engine.mode == SessionMode.VERBOSE
        assert engine.ui.verbose_worker is True

    def test_handle_slash_command_quiet(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._handle_slash_command("/verbose")
        result = engine._handle_slash_command("/quiet")
        assert result is True
        assert engine.mode == SessionMode.AUTO
        assert engine.ui.verbose_worker is False

    def test_handle_slash_command_unknown(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/nonexistent")
        assert result is False

    def test_handle_slash_command_clear(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._init_manager()
        engine.manager.messages.append(
            MagicMock(role=MagicMock(value="user"), content="test")
        )
        result = engine._handle_slash_command("/clear")
        assert result is True
        # Manager should only have the system prompt
        assert len(engine.manager.messages) == 1

"""Tests for CommandHandler - command routing and dispatch."""

from unittest.mock import MagicMock, patch

import pytest

from src.commands.parser import Command
from src.commands.handlers import CommandHandler


@pytest.fixture
def mock_engine():
    """Create a mock SessionEngine with required attributes."""
    engine = MagicMock()
    engine.ui = MagicMock()
    engine.settings = MagicMock()
    engine.manager = MagicMock()
    engine.worker_registry = MagicMock()
    engine.session_name = "test-session"
    engine.session_id = "test-id-123"
    engine._confirm_mode = False
    return engine


@pytest.fixture
def handler(mock_engine):
    return CommandHandler(mock_engine)


class TestSourceRouting:
    """Tests for handle() source-based routing."""

    def test_manager_source(self, handler, mock_engine):
        cmd = Command(source="manager", action="show", args=[], options={})
        mock_engine._manager_show_config.return_value = True
        result = handler.handle(cmd)
        assert result is True

    def test_worker_source(self, handler, mock_engine):
        cmd = Command(source="worker", action="list", args=[], options={})
        mock_engine._show_worker_list.return_value = True
        result = handler.handle(cmd)
        assert result is True

    def test_session_source(self, handler, mock_engine):
        cmd = Command(source="session", action="show", args=[], options={})
        result = handler.handle(cmd)
        assert result is True

    def test_system_source(self, handler, mock_engine):
        cmd = Command(source="system", action="show", args=[], options={})
        result = handler.handle(cmd)
        assert result is True

    def test_mode_source(self, handler, mock_engine):
        cmd = Command(source="mode", action="verbose", args=[], options={})
        result = handler.handle(cmd)
        assert result is True
        assert mock_engine.ui.verbose_worker is True

    def test_submanager_source(self, handler, mock_engine):
        cmd = Command(source="submanager", action="list", args=[], options={})
        mock_engine._handle_submanager_command.return_value = True
        result = handler.handle(cmd)
        assert result is True

    def test_team_source(self, handler, mock_engine):
        cmd = Command(source="team", action="list", args=[], options={})
        mock_engine._handle_team_command.return_value = True
        result = handler.handle(cmd)
        assert result is True

    def test_unknown_source(self, handler, mock_engine):
        cmd = Command(source="unknown", action="show", args=[], options={})
        result = handler.handle(cmd)
        assert result is False
        mock_engine.ui.print_error.assert_called()


class TestManagerActions:
    """Tests for manager command actions."""

    def test_manager_show(self, handler, mock_engine):
        cmd = Command(source="manager", action="show", args=[], options={})
        mock_engine._manager_show_config.return_value = True
        result = handler.handle(cmd)
        mock_engine._manager_show_config.assert_called_once()

    def test_manager_set_profile(self, handler, mock_engine):
        cmd = Command(source="manager", action="set profile", args=["advanced"], options={})
        mock_engine._manager_set_profile.return_value = True
        result = handler.handle(cmd)
        mock_engine._manager_set_profile.assert_called_once_with("advanced")

    def test_manager_set_profile_missing_args(self, handler, mock_engine):
        cmd = Command(source="manager", action="set profile", args=[], options={})
        result = handler.handle(cmd)
        assert result is False
        mock_engine.ui.print_error.assert_called()

    def test_manager_set_model(self, handler, mock_engine):
        cmd = Command(source="manager", action="set model", args=["gpt-4o"], options={"--global": ""})
        mock_engine._manager_set_model.return_value = True
        result = handler.handle(cmd)
        mock_engine._manager_set_model.assert_called_once_with("gpt-4o", persistent=True)

    def test_manager_set_api(self, handler, mock_engine):
        cmd = Command(source="manager", action="set api", args=["http://localhost:8080"], options={})
        mock_engine._manager_set_api.return_value = True
        result = handler.handle(cmd)
        mock_engine._manager_set_api.assert_called_once()

    def test_manager_unknown_action(self, handler, mock_engine):
        cmd = Command(source="manager", action="nonexistent", args=[], options={})
        result = handler.handle(cmd)
        assert result is False


class TestWorkerActions:
    """Tests for worker command actions."""

    def test_worker_list(self, handler, mock_engine):
        cmd = Command(source="worker", action="list", args=[], options={})
        mock_engine._show_worker_list.return_value = True
        result = handler.handle(cmd)
        mock_engine._show_worker_list.assert_called_once()

    def test_worker_add(self, handler, mock_engine):
        cmd = Command(source="worker", action="add", args=["coder", "gemini-pro", "live"], options={})
        mock_engine._handle_worker_command.return_value = True
        result = handler.handle(cmd)
        assert result is True

    def test_worker_remove(self, handler, mock_engine):
        cmd = Command(source="worker", action="remove", args=["coder"], options={})
        mock_engine._handle_worker_command.return_value = True
        result = handler.handle(cmd)
        assert result is True

    def test_worker_unknown_action(self, handler, mock_engine):
        cmd = Command(source="worker", action="nonexistent", args=[], options={})
        result = handler.handle(cmd)
        assert result is False


class TestModeActions:
    """Tests for mode command actions."""

    def test_mode_verbose(self, handler, mock_engine):
        cmd = Command(source="mode", action="verbose", args=[], options={})
        result = handler.handle(cmd)
        assert result is True

    def test_mode_quiet(self, handler, mock_engine):
        cmd = Command(source="mode", action="quiet", args=[], options={})
        result = handler.handle(cmd)
        assert result is True

    def test_mode_confirm_on(self, handler, mock_engine):
        cmd = Command(source="mode", action="confirm on", args=[], options={})
        result = handler.handle(cmd)
        assert result is True

    def test_mode_confirm_off(self, handler, mock_engine):
        cmd = Command(source="mode", action="confirm off", args=[], options={})
        result = handler.handle(cmd)
        assert result is True

    def test_mode_unknown(self, handler, mock_engine):
        cmd = Command(source="mode", action="invalid", args=[], options={})
        result = handler.handle(cmd)
        assert result is False


class TestSessionActions:
    """Tests for session command actions."""

    def test_session_show(self, handler, mock_engine):
        cmd = Command(source="session", action="show", args=[], options={})
        result = handler.handle(cmd)
        assert result is True

    def test_session_save(self, handler, mock_engine):
        cmd = Command(source="session", action="save", args=["my-session"], options={})
        result = handler.handle(cmd)
        mock_engine.save_session.assert_called_once()

    def test_session_load_missing_args(self, handler, mock_engine):
        cmd = Command(source="session", action="load", args=[], options={})
        result = handler.handle(cmd)
        assert result is False


class TestSystemActions:
    """Tests for system command actions."""

    def test_system_show(self, handler, mock_engine):
        cmd = Command(source="system", action="show", args=[], options={})
        result = handler.handle(cmd)
        assert result is True

    def test_system_validate_no_issues(self, handler, mock_engine):
        mock_engine.settings.validate_config.return_value = []
        cmd = Command(source="system", action="validate", args=[], options={})
        result = handler.handle(cmd)
        assert result is True

    def test_system_validate_with_issues(self, handler, mock_engine):
        mock_engine.settings.validate_config.return_value = [
            {"level": "error", "message": "test error"}
        ]
        cmd = Command(source="system", action="validate", args=[], options={})
        result = handler.handle(cmd)
        assert result is False

"""Tests for the Agent Worker module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.core.worker import AgentWorker, TaskResult, TaskStatus, _NOISE_PATTERNS


class TestBuildCommand:
    """Tests for AgentWorker._build_command()."""

    def test_default_profile(self):
        settings = MagicMock()
        settings.WORKER_PROFILE = "live"
        worker = AgentWorker(settings=settings)
        cmd = worker._build_command("fix the bug", "claude-3-5-sonnet-20241022")
        assert cmd == [
            "uv", "run", "mini", "--headless",
            "--profile", "live",
            "--model", "claude-3-5-sonnet-20241022",
            "--task", "fix the bug",
        ]

    def test_profile_override(self):
        settings = MagicMock()
        settings.WORKER_PROFILE = "live"
        worker = AgentWorker(settings=settings)
        cmd = worker._build_command("fix the bug", "claude-3-5-sonnet-20241022", profile="livesweagent")
        assert cmd[5] == "livesweagent"  # --profile value

    def test_task_with_special_chars(self):
        settings = MagicMock()
        settings.WORKER_PROFILE = "live"
        worker = AgentWorker(settings=settings)
        cmd = worker._build_command('fix "the bug" in app.py', "model")
        assert cmd[-1] == 'fix "the bug" in app.py'


class TestBuildEnv:
    """Tests for AgentWorker._build_env() allowlist."""

    def test_only_allowlisted_vars(self):
        settings = MagicMock()
        settings.get_agent_env.return_value = {"MINI_API_BASE": "http://localhost"}
        worker = AgentWorker(settings=settings)
        with patch.dict("os.environ", {"PATH": "/usr/bin", "SECRET_KEY": "should-not-pass", "HOME": "/home/user"}, clear=True):
            env = worker._build_env()
        assert "PATH" in env
        assert "HOME" in env
        assert "SECRET_KEY" not in env
        assert "LITELLM_LOG" in env
        assert env["LITELLM_LOG"] == "ERROR"

    def test_api_overrides(self):
        settings = MagicMock()
        settings.get_agent_env.return_value = {}
        worker = AgentWorker(settings=settings)
        with patch.dict("os.environ", {"PATH": "/usr/bin"}, clear=True):
            env = worker._build_env(api_base_override="https://api.z.ai/v1/", api_key_override="sk-test")
        assert env["MINI_API_BASE"] == "https://api.z.ai/v1"  # trailing slash stripped
        assert env["MINI_API_KEY"] == "sk-test"

    def test_no_api_overrides(self):
        settings = MagicMock()
        settings.get_agent_env.return_value = {}
        worker = AgentWorker(settings=settings)
        with patch.dict("os.environ", {"PATH": "/usr/bin"}, clear=True):
            env = worker._build_env()
        assert "MINI_API_BASE" not in env
        assert "MINI_API_KEY" not in env


class TestIsNoiseLine:
    """Tests for AgentWorker._is_noise_line() filtering."""

    def test_noise_patterns_filtered(self):
        for pattern in _NOISE_PATTERNS:
            assert AgentWorker._is_noise_line(f"  {pattern}  ") is True

    def test_normal_line_not_filtered(self):
        assert AgentWorker._is_noise_line("Step 1: Reading file app.py") is False
        assert AgentWorker._is_noise_line("Writing to output.txt") is False

    def test_empty_line_not_noise(self):
        assert AgentWorker._is_noise_line("") is False
        assert AgentWorker._is_noise_line("   ") is False

    def test_ansi_escape_stripped(self):
        ansi_line = "\x1b[31mProvider List: https://docs.litellm.ai\x1b[0m"
        assert AgentWorker._is_noise_line(ansi_line) is True


class TestTerminateProcess:
    """Tests for AgentWorker._terminate_process()."""

    def test_already_terminated(self):
        settings = MagicMock()
        worker = AgentWorker(settings=settings)
        process = MagicMock()
        process.poll.return_value = 0  # already terminated
        worker._terminate_process(process)
        process.terminate.assert_not_called()

    def test_graceful_terminate(self):
        settings = MagicMock()
        worker = AgentWorker(settings=settings)
        process = MagicMock()
        process.poll.return_value = None  # still running
        process.wait.return_value = None
        worker._terminate_process(process)
        process.terminate.assert_called_once()

    def test_force_kill_on_timeout(self):
        settings = MagicMock()
        worker = AgentWorker(settings=settings)
        process = MagicMock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired(cmd="test", timeout=5), None]
        worker._terminate_process(process)
        process.terminate.assert_called_once()
        process.kill.assert_called_once()


class TestTaskResult:
    """Tests for TaskResult dataclass."""

    def test_success_result(self):
        result = TaskResult(
            status=TaskStatus.SUCCESS, exit_code=0,
            output_lines=["line1", "line2"], step_count=3,
            total_cost=0.02, duration_seconds=5.0,
        )
        assert result.is_success is True
        assert result.output_text == "line1\nline2"
        assert "✓" in result.summary
        assert "3" in result.summary

    def test_failed_result(self):
        result = TaskResult(
            status=TaskStatus.FAILED, exit_code=1,
            error_message="Something went wrong",
        )
        assert result.is_success is False
        assert "✗" in result.summary

    def test_cancelled_result(self):
        result = TaskResult(
            status=TaskStatus.CANCELLED, exit_code=130,
        )
        assert result.is_success is False

    def test_empty_output(self):
        result = TaskResult(status=TaskStatus.SUCCESS, exit_code=0)
        assert result.output_text == ""
        assert result.output_lines == []


class TestRunTask:
    """Tests for AgentWorker.run_task() with mocked subprocess."""

    def test_file_not_found_error(self):
        settings = MagicMock()
        settings.WORKER_PROFILE = "live"
        settings.WORKER_TIMEOUT = 600
        settings.agent_path_resolved = Path("/nonexistent/path")
        worker = AgentWorker(settings=settings)
        result = worker.run_task("test task", "model")
        assert result.status == TaskStatus.FAILED
        assert result.exit_code == -1
        assert "does not exist" in result.error_message

    def test_keyboard_interrupt(self):
        settings = MagicMock()
        settings.WORKER_PROFILE = "live"
        settings.WORKER_TIMEOUT = 600
        settings.agent_path_resolved = MagicMock()
        settings.agent_path_resolved.exists.return_value = True
        worker = AgentWorker(settings=settings)
        with patch.object(worker, "run", side_effect=KeyboardInterrupt):
            result = worker.run_task("test task", "model")
        assert result.status == TaskStatus.CANCELLED
        assert result.exit_code == 130

    def test_runtime_error(self):
        settings = MagicMock()
        settings.WORKER_PROFILE = "live"
        settings.WORKER_TIMEOUT = 600
        settings.agent_path_resolved = MagicMock()
        settings.agent_path_resolved.exists.return_value = True
        worker = AgentWorker(settings=settings)
        with patch.object(worker, "run", side_effect=RuntimeError("uv not installed")):
            result = worker.run_task("test task", "model")
        assert result.status == TaskStatus.FAILED
        assert "uv not installed" in result.error_message


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.SUCCESS.value == "success"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"

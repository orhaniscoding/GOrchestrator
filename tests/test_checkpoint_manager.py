"""Tests for CheckpointManager - git-based checkpoint/undo system."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.core.checkpoint_manager import CheckpointManager


class TestIsGitRepo:
    """Tests for is_git_repo() with caching."""

    @patch("src.core.checkpoint_manager.subprocess.run")
    def test_is_git_repo_true(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        cm = CheckpointManager(Path("/fake/dir"))
        # _load_from_git also calls is_git_repo, so reset cache
        cm._git_repo_cached = None
        assert cm.is_git_repo() is True

    @patch("src.core.checkpoint_manager.subprocess.run")
    def test_is_git_repo_false(self, mock_run):
        mock_run.return_value = MagicMock(returncode=128)
        cm = CheckpointManager(Path("/fake/dir"))
        cm._git_repo_cached = None
        assert cm.is_git_repo() is False

    @patch("src.core.checkpoint_manager.subprocess.run")
    def test_is_git_repo_cached(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        cm = CheckpointManager(Path("/fake/dir"))
        cm._git_repo_cached = True
        # Should not call subprocess again
        result = cm.is_git_repo()
        assert result is True

    @patch("src.core.checkpoint_manager.subprocess.run")
    def test_is_git_repo_exception(self, mock_run):
        mock_run.side_effect = OSError("git not found")
        cm = CheckpointManager(Path("/fake/dir"))
        cm._git_repo_cached = None
        assert cm.is_git_repo() is False


class TestCreate:
    """Tests for create() with returncode checks."""

    @patch("src.core.checkpoint_manager.subprocess.run")
    def test_create_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        cm = CheckpointManager(Path("/fake/dir"))
        cm._git_repo_cached = True
        result = cm.create("test-label")
        assert result is not None
        assert result.startswith("gorchestrator-checkpoint-")
        assert result in cm.stack

    @patch("src.core.checkpoint_manager.subprocess.run")
    def test_create_not_git_repo(self, mock_run):
        mock_run.return_value = MagicMock(returncode=128)
        cm = CheckpointManager(Path("/fake/dir"))
        cm._git_repo_cached = False
        result = cm.create()
        assert result is None

    @patch("src.core.checkpoint_manager.subprocess.run")
    def test_create_git_add_fails(self, mock_run):
        """create() should return None if git add fails."""
        cm = CheckpointManager(Path("/fake/dir"))
        cm._git_repo_cached = True
        # First call (git add) fails
        mock_run.return_value = MagicMock(returncode=1)
        result = cm.create()
        assert result is None

    @patch("src.core.checkpoint_manager.subprocess.run")
    def test_create_git_commit_fails(self, mock_run):
        """create() should return None if git commit fails."""
        cm = CheckpointManager(Path("/fake/dir"))
        cm._git_repo_cached = True
        # git add succeeds, git commit fails
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git add
            MagicMock(returncode=1),  # git commit
        ]
        result = cm.create()
        assert result is None

    @patch("src.core.checkpoint_manager.subprocess.run")
    def test_create_git_tag_fails(self, mock_run):
        """create() should return None if git tag fails."""
        cm = CheckpointManager(Path("/fake/dir"))
        cm._git_repo_cached = True
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git add
            MagicMock(returncode=0),  # git commit
            MagicMock(returncode=1),  # git tag
        ]
        result = cm.create()
        assert result is None


class TestRestore:
    """Tests for restore() with peek-then-pop pattern."""

    @patch("src.core.checkpoint_manager.subprocess.run")
    def test_restore_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        cm = CheckpointManager(Path("/fake/dir"))
        cm._git_repo_cached = True
        cm._checkpoint_stack = ["gorchestrator-checkpoint-20250101_120000"]
        success, msg = cm.restore()
        assert success is True
        assert "Restored" in msg
        assert len(cm.stack) == 0  # popped on success

    @patch("src.core.checkpoint_manager.subprocess.run")
    def test_restore_empty_stack(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        cm = CheckpointManager(Path("/fake/dir"))
        cm._git_repo_cached = True
        cm._checkpoint_stack = []
        success, msg = cm.restore()
        assert success is False
        assert "No checkpoints" in msg

    @patch("src.core.checkpoint_manager.subprocess.run")
    def test_restore_git_reset_fails(self, mock_run):
        """restore() should NOT pop stack if git reset fails."""
        cm = CheckpointManager(Path("/fake/dir"))
        cm._git_repo_cached = True
        tag = "gorchestrator-checkpoint-20250101_120000"
        cm._checkpoint_stack = [tag]
        mock_run.return_value = MagicMock(returncode=1)
        success, msg = cm.restore()
        assert success is False
        assert "git reset failed" in msg
        assert tag in cm.stack  # NOT popped

    @patch("src.core.checkpoint_manager.subprocess.run")
    def test_restore_not_git_repo(self, mock_run):
        mock_run.return_value = MagicMock(returncode=128)
        cm = CheckpointManager(Path("/fake/dir"))
        cm._git_repo_cached = False
        cm._checkpoint_stack = ["gorchestrator-checkpoint-20250101_120000"]
        success, msg = cm.restore()
        assert success is False


class TestListCheckpoints:
    """Tests for list_checkpoints()."""

    @patch("src.core.checkpoint_manager.subprocess.run")
    def test_list_checkpoints(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="gorchestrator-checkpoint-20250101_120000\ngorchestrator-checkpoint-20250102_120000\n",
        )
        cm = CheckpointManager(Path("/fake/dir"))
        cm._git_repo_cached = True
        result = cm.list_checkpoints()
        assert len(result) == 2

    @patch("src.core.checkpoint_manager.subprocess.run")
    def test_list_checkpoints_not_git(self, mock_run):
        mock_run.return_value = MagicMock(returncode=128)
        cm = CheckpointManager(Path("/fake/dir"))
        cm._git_repo_cached = False
        result = cm.list_checkpoints()
        assert result == []


class TestLoadFromGit:
    """Tests for _load_from_git()."""

    @patch("src.core.checkpoint_manager.subprocess.run")
    def test_load_from_git_filters_invalid_tags(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="gorchestrator-checkpoint-20250101_120000\ngorchestrator-checkpoint-INVALID\n",
        )
        cm = CheckpointManager(Path("/fake/dir"))
        cm._git_repo_cached = True
        cm._checkpoint_stack = []
        cm._load_from_git()
        assert len(cm.stack) == 1
        assert cm.stack[0] == "gorchestrator-checkpoint-20250101_120000"

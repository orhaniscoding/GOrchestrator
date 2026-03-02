"""
Checkpoint Manager - Git-based checkpoint system for Worker task safety.

Creates git tag checkpoints before Worker tasks run, allowing users
to undo changes with /undo. Checkpoints are stored as git tags with
the prefix 'gorchestrator-checkpoint-'.
"""

import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages git-based checkpoints for safe Worker task execution."""

    _TAG_PREFIX = "gorchestrator-checkpoint-"
    _TAG_PATTERN = re.compile(r'^gorchestrator-checkpoint-\d{8}_\d{6}$')

    def __init__(self, work_dir: Path):
        """
        Initialize CheckpointManager.

        Args:
            work_dir: The working directory for git operations (agent_path_resolved).
        """
        self._work_dir = work_dir
        self._checkpoint_stack: list[str] = []
        self._git_repo_cached: bool | None = None
        self._load_from_git()

    @property
    def stack(self) -> list[str]:
        """Access the checkpoint stack (for external inspection)."""
        return self._checkpoint_stack

    def is_git_repo(self) -> bool:
        """Check if we are inside a git repository (cached)."""
        if self._git_repo_cached is not None:
            return self._git_repo_cached
        try:
            cwd = str(self._work_dir) if self._work_dir.exists() else "."
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=cwd, capture_output=True, timeout=5,
            )
            self._git_repo_cached = result.returncode == 0
        except Exception:
            self._git_repo_cached = False
        return self._git_repo_cached

    def create(self, label: str = "") -> str | None:
        """Create a git stash checkpoint before Worker runs."""
        if not self.is_git_repo():
            return None
        try:
            work_dir = str(self._work_dir)
            # Stage all changes including untracked
            result = subprocess.run(["git", "add", "-A"], cwd=work_dir, capture_output=True, timeout=10)
            if result.returncode != 0:
                logger.warning(f"git add failed (rc={result.returncode})")
                return None
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            tag_name = f"{self._TAG_PREFIX}{ts}"
            msg = f"GOrchestrator checkpoint: {label or ts}"
            # Create a commit for the checkpoint
            result = subprocess.run(
                ["git", "commit", "--allow-empty", "-m", msg],
                cwd=work_dir, capture_output=True, timeout=10,
            )
            if result.returncode != 0:
                logger.warning(f"git commit failed (rc={result.returncode})")
                return None
            # Tag it for easy reference
            result = subprocess.run(
                ["git", "tag", tag_name],
                cwd=work_dir, capture_output=True, timeout=10,
            )
            if result.returncode != 0:
                logger.warning(f"git tag failed (rc={result.returncode})")
                return None
            self._checkpoint_stack.append(tag_name)
            logger.info(f"Checkpoint created: {tag_name}")
            return tag_name
        except Exception as e:
            logger.warning(f"Failed to create checkpoint: {e}")
            return None

    def _load_from_git(self):
        """Load existing checkpoint tags from git on startup."""
        if not self.is_git_repo():
            return
        try:
            work_dir = str(self._work_dir)
            result = subprocess.run(
                ["git", "tag", "--list", f"{self._TAG_PREFIX}*", "--sort=creatordate"],
                cwd=work_dir, capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                tags = result.stdout.strip().splitlines()
                tags = [t for t in tags if self._TAG_PATTERN.match(t)]
                self._checkpoint_stack = tags
                logger.info(f"Loaded {len(tags)} checkpoints from git tags")
        except Exception as e:
            logger.warning(f"Failed to load checkpoints from git: {e}")

    def list_checkpoints(self) -> list[str]:
        """List all available checkpoint tags from git."""
        if not self.is_git_repo():
            return []
        try:
            work_dir = str(self._work_dir)
            result = subprocess.run(
                ["git", "tag", "--list", f"{self._TAG_PREFIX}*", "--sort=-creatordate"],
                cwd=work_dir, capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().splitlines()
        except Exception:
            pass
        return []

    def restore(self) -> tuple[bool, str]:
        """
        Restore the last checkpoint (undo last Worker changes).

        Returns:
            Tuple of (success, message).
        """
        # Refresh from git tags if in-memory stack is empty
        if not self._checkpoint_stack:
            self._load_from_git()
        if not self._checkpoint_stack:
            return False, "No checkpoints available to restore."
        if not self.is_git_repo():
            return False, "Not a git repository. Cannot restore checkpoint."
        try:
            tag_name = self._checkpoint_stack[-1]  # peek, don't pop yet
            work_dir = str(self._work_dir)
            result = subprocess.run(
                ["git", "reset", "--hard", tag_name],
                cwd=work_dir, capture_output=True, timeout=10,
            )
            if result.returncode != 0:
                return False, f"git reset failed (rc={result.returncode})"
            self._checkpoint_stack.pop()  # only pop on success
            logger.info(f"Restored checkpoint: {tag_name}")
            return True, f"Restored checkpoint: {tag_name}"
        except Exception as e:
            logger.error(f"Failed to restore checkpoint: {e}")
            return False, f"Failed to restore: {e}"

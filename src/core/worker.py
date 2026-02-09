"""
Agent Worker - Subprocess wrapper for Mini-SWE-GOCore.
Handles spawning the agent process with proper environment injection and real-time output streaming.
"""

import logging
import os
import signal
import subprocess
import time
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

from .config import Settings, get_settings


class TaskStatus(Enum):
    """Status of a task execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """Structured result from an agent task execution."""
    status: TaskStatus
    exit_code: int
    output_lines: list[str] = field(default_factory=list)
    total_cost: float = 0.0
    step_count: int = 0
    duration_seconds: float = 0.0
    error_message: str | None = None

    @property
    def is_success(self) -> bool:
        return self.status == TaskStatus.SUCCESS

    @property
    def output_text(self) -> str:
        """Get all output as a single string."""
        return "\n".join(self.output_lines)

    @property
    def summary(self) -> str:
        """Get a brief summary of the result."""
        status_emoji = "✓" if self.is_success else "✗"
        return (
            f"{status_emoji} Status: {self.status.value} | "
            f"Steps: {self.step_count} | "
            f"Cost: ${self.total_cost:.4f} | "
            f"Duration: {self.duration_seconds:.1f}s"
        )


class AgentWorker:
    """
    Wrapper class for running Mini-SWE-GOCore agent as a subprocess.
    Provides real-time streaming of agent output.
    """

    def __init__(self, settings: Settings | None = None):
        """
        Initialize AgentWorker with settings.

        Args:
            settings: Optional Settings instance. If None, uses default settings.
        """
        self.settings = settings or get_settings()

    def _build_command(self, task: str, model: str) -> list[str]:
        """
        Build the command to run the agent.

        Args:
            task: The task description for the agent.
            model: The model to use (e.g., 'claude-3-5-sonnet-20241022').

        Returns:
            List of command arguments.
        """
        return [
            "uv",
            "run",
            "mini",
            "--headless",
            "--profile",
            self.settings.WORKER_PROFILE,
            "--model",
            model,
            "--task",
            task,
        ]

    def _build_env(self) -> dict[str, str]:
        """
        Build the environment variables for the subprocess.
        Merges current environment with agent-specific variables.

        Returns:
            Dictionary of environment variables.
        """
        env = os.environ.copy()
        env.update(self.settings.get_agent_env())
        return env

    def _terminate_process(self, process: subprocess.Popen):
        """Gracefully terminate a subprocess, force kill if needed."""
        if process.poll() is not None:
            return
        try:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Worker process did not terminate, force killing...")
                process.kill()
                process.wait(timeout=3)
        except Exception as e:
            logger.error(f"Failed to terminate worker process: {e}")

    def run(
        self,
        task: str,
        model: str = "claude-3-5-sonnet-20241022",
        on_output: Callable[[str], None] | None = None,
    ) -> Generator[str, None, int]:
        """
        Run the agent with the given task and stream output in real-time.

        Args:
            task: The task description for the agent to execute.
            model: The model to use. Defaults to claude-3-5-sonnet.
            on_output: Optional callback for each output line.

        Yields:
            Output lines from the agent process as they arrive.

        Returns:
            The exit code of the subprocess.
        """
        command = self._build_command(task, model)
        env = self._build_env()
        agent_path = self.settings.agent_path_resolved

        if not agent_path.exists():
            raise FileNotFoundError(
                f"Agent path does not exist: {agent_path}\n"
                f"Please ensure AGENT_PATH is set correctly in your .env file."
            )

        process = None
        try:
            process = subprocess.Popen(
                command,
                cwd=agent_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
            )

            if process.stdout:
                for line in process.stdout:
                    clean_line = line.rstrip("\n\r")
                    if on_output:
                        on_output(clean_line)
                    yield clean_line

            process.wait()
            return process.returncode

        except KeyboardInterrupt:
            if process:
                self._terminate_process(process)
            raise
        except FileNotFoundError as e:
            if "uv" in str(e):
                raise RuntimeError(
                    "uv is not installed or not in PATH. "
                    "Please install it: https://github.com/astral-sh/uv"
                ) from e
            raise
        finally:
            if process and process.poll() is None:
                self._terminate_process(process)

    def run_task(
        self,
        task: str,
        model: str = "claude-3-5-sonnet-20241022",
        on_output: Callable[[str], None] | None = None,
    ) -> TaskResult:
        """
        Run the agent and return a structured TaskResult.

        Args:
            task: The task description for the agent to execute.
            model: The model to use.
            on_output: Optional callback for each output line (for streaming to UI).

        Returns:
            TaskResult with status, output, cost, and other metrics.
        """
        from ..utils.parser import parse_log_line

        output_lines: list[str] = []
        step_count = 0
        total_cost = 0.0
        start_time = time.time()
        exit_code = 0
        error_message = None

        try:
            gen = self.run(task, model, on_output)
            timeout = self.settings.WORKER_TIMEOUT

            for line in gen:
                output_lines.append(line)

                # Check timeout
                if timeout > 0 and (time.time() - start_time) > timeout:
                    logger.warning(f"Worker task timed out after {timeout}s")
                    gen.close()
                    return TaskResult(
                        status=TaskStatus.FAILED,
                        exit_code=-2,
                        output_lines=output_lines,
                        step_count=step_count,
                        total_cost=total_cost,
                        duration_seconds=time.time() - start_time,
                        error_message=f"Task timed out after {timeout} seconds",
                    )

                # Parse line to extract metrics
                entry = parse_log_line(line)
                if hasattr(entry, "is_step") and entry.is_step:
                    step_count += 1
                if hasattr(entry, "cost") and entry.cost:
                    total_cost = entry.cost

            # Get exit code from generator
            try:
                next(gen)
            except StopIteration as e:
                exit_code = e.value if e.value is not None else 0

        except FileNotFoundError as e:
            error_message = str(e)
            return TaskResult(
                status=TaskStatus.FAILED,
                exit_code=-1,
                output_lines=output_lines,
                error_message=error_message,
                duration_seconds=time.time() - start_time,
            )
        except RuntimeError as e:
            error_message = str(e)
            return TaskResult(
                status=TaskStatus.FAILED,
                exit_code=-1,
                output_lines=output_lines,
                error_message=error_message,
                duration_seconds=time.time() - start_time,
            )
        except KeyboardInterrupt:
            return TaskResult(
                status=TaskStatus.CANCELLED,
                exit_code=130,
                output_lines=output_lines,
                step_count=step_count,
                total_cost=total_cost,
                duration_seconds=time.time() - start_time,
            )

        duration = time.time() - start_time
        status = TaskStatus.SUCCESS if exit_code == 0 else TaskStatus.FAILED

        return TaskResult(
            status=status,
            exit_code=exit_code,
            output_lines=output_lines,
            total_cost=total_cost,
            step_count=step_count,
            duration_seconds=duration,
            error_message=error_message,
        )

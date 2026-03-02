"""Headless agent with JSON Lines output for automation/CI pipelines.

This agent is designed for:
- CI/CD pipelines
- API backends
- Script automation
- GUI orchestrators (like GOrchestrator)

No TUI dependencies (no rich, no prompt_toolkit, no textual).
All output is structured JSON Lines to stdout.

Output events:
- {"type": "start", "data": {"task": "...", "model": "..."}}
- {"type": "step", "data": {"step": 1, "action": "...", "output": "..."}}
- {"type": "thought", "data": {"content": "..."}}
- {"type": "log", "level": "info", "content": "..."}
- {"type": "finish", "data": {"status": "success", "result": "..."}}
- {"type": "error", "data": {"error": "...", "type": "...", "traceback": "..."}}
- {"type": "cost", "data": {"total": 0.05, "calls": 10}}
"""

import json
import re
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, TextIO

from minisweagent import Model, Environment
from minisweagent.agents.default import (
    DefaultAgent,
    AgentConfig,
    NonTerminatingException,
    TerminatingException,
)


@dataclass
class JsonOutputHandler:
    """Output handler that writes JSON Lines to stdout.

    Each line is a valid JSON object with:
    - type: Event type (start, step, thought, log, finish, error, cost)
    - data: Event-specific data
    - timestamp: ISO 8601 timestamp (optional)
    """

    stream: TextIO = field(default_factory=lambda: sys.stdout)
    include_timestamp: bool = True

    def emit(self, event_type: str, data: dict, **extra) -> None:
        """Emit a JSON event to stdout."""
        event = {
            "type": event_type,
            "data": data,
            **extra
        }
        if self.include_timestamp:
            event["timestamp"] = datetime.now(timezone.utc).isoformat()

        try:
            line = json.dumps(event, ensure_ascii=False, default=str)
            self.stream.write(line + "\n")
            self.stream.flush()
        except Exception as e:
            # Fallback: write error as plain text to stderr
            sys.stderr.write(f"JSON output error: {e}\n")
            sys.stderr.flush()

    def log(self, level: str, content: str) -> None:
        """Emit a log event."""
        self.emit("log", {"level": level, "content": content})

    def info(self, content: str) -> None:
        self.log("info", content)

    def warning(self, content: str) -> None:
        self.log("warning", content)

    def error(self, content: str) -> None:
        self.log("error", content)

    def flush(self) -> None:
        self.stream.flush()


@dataclass
class HeadlessAgentConfig(AgentConfig):
    """Configuration for headless agent."""

    # Headless mode always runs without confirmation
    mode: str = "yolo"
    confirm_exit: bool = False

    # Output settings
    include_timestamps: bool = True
    max_output_length: int = 10000
    """Truncate long outputs to this length"""


class HeadlessAgent(DefaultAgent):
    """Headless agent for automation and CI/CD pipelines.

    Features:
    - No TUI dependencies
    - JSON Lines output to stdout
    - Suitable for: CI/CD, scripts, API backends, GUI orchestrators

    Usage:
        agent = HeadlessAgent(model, env)
        exit_status, result = agent.run("Fix the bug")
        # Output is streamed as JSON Lines to stdout
    """

    def __init__(
        self,
        model: Model,
        env: Environment,
        output_handler: Optional[JsonOutputHandler] = None,
        **kwargs
    ):
        # Use HeadlessAgentConfig by default
        kwargs.setdefault("config_class", HeadlessAgentConfig)
        super().__init__(model, env, **kwargs)

        self.output = output_handler or JsonOutputHandler(
            include_timestamp=getattr(self.config, "include_timestamps", True)
        )
        self._step_count = 0

    def run(self, task: str, **kwargs) -> tuple[str, str]:
        """Run the agent with JSON output."""
        # Emit start event
        self.output.emit("start", {
            "task": task,
            "model": getattr(self.model.config, "model_name", "unknown"),
            "workdir": str(kwargs.get("cwd", ".")),
        })

        try:
            exit_status, result = self._run_internal(task, **kwargs)

            # Emit finish event
            self.output.emit("finish", {
                "status": exit_status,
                "result": result,
            })

            # Emit cost summary
            self.output.emit("cost", {
                "total": self.model.cost,
                "calls": self.model.n_calls,
            })

            return exit_status, result

        except Exception as e:
            # Emit error event
            self.output.emit("error", {
                "error": str(e),
                "type": type(e).__name__,
                "traceback": traceback.format_exc(),
            })
            raise

    def _run_internal(self, task: str, **kwargs) -> tuple[str, str]:
        """Internal run logic (same as DefaultAgent.run but with hooks)."""
        self.extra_template_vars |= {"task": task, **kwargs}
        self.messages = []
        self.add_message("system", self.render_template(self.config.system_template))
        self.add_message("user", self.render_template(self.config.instance_template))

        while True:
            try:
                self.step()
            except NonTerminatingException as e:
                self.add_message("user", str(e))
                self.output.emit("log", {"level": "warning", "content": str(e)})
            except TerminatingException as e:
                self.add_message("user", str(e))
                return type(e).__name__, str(e)

    def step(self) -> dict:
        """Execute one agent step with JSON output."""
        self._step_count += 1

        # Query model
        response = self.query()
        content = response.get("content", "")

        # Extract and emit thoughts (if any)
        self._emit_thoughts(content)

        # Get observation
        observation = self.get_observation(response)

        # Emit step event
        action = observation.get("action", "")
        output = observation.get("output", "")

        # Truncate long outputs
        max_len = getattr(self.config, "max_output_length", 10000)
        if len(output) > max_len:
            output = output[:max_len] + f"\n... (truncated, {len(output)} total chars)"

        self.output.emit("step", {
            "step": self._step_count,
            "action": action[:500],  # Truncate action for readability
            "output": output,
            "cost_so_far": self.model.cost,
        })

        return observation

    def _emit_thoughts(self, content: str) -> None:
        """Extract and emit thought blocks from model response."""
        # Look for <thought>...</thought> or <thinking>...</thinking> blocks
        patterns = [
            r"<thought>(.*?)</thought>",
            r"<thinking>(.*?)</thinking>",
        ]

        for pattern in patterns:
            thoughts = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
            for thought in thoughts:
                self.output.emit("thought", {"content": thought.strip()})


# Backward compatibility alias
JsonAgent = HeadlessAgent


__all__ = ["HeadlessAgent", "JsonAgent", "JsonOutputHandler", "HeadlessAgentConfig"]

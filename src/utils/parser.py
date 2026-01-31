"""
JSON Log Parser for Mini-SWE-GOCore output.
Parses structured JSON logs from the agent and provides typed access to log data.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

# Configure module logger
logger = logging.getLogger(__name__)


@dataclass
class AgentLogEntry:
    """Structured representation of an agent log entry."""

    log_type: str
    data: dict[str, Any]
    raw: str

    @property
    def is_step(self) -> bool:
        return self.log_type == "step"

    @property
    def is_result(self) -> bool:
        return self.log_type == "result"

    @property
    def is_cost(self) -> bool:
        return self.log_type == "cost"

    @property
    def is_error(self) -> bool:
        return self.log_type == "error"

    @property
    def step_number(self) -> int | None:
        """Get step number if this is a step log."""
        if self.is_step:
            return self.data.get("step")
        return None

    @property
    def message(self) -> str | None:
        """Get message content if available."""
        return self.data.get("message") or self.data.get("content")

    @property
    def cost(self) -> float | None:
        """Get cost value if this is a cost log."""
        if self.is_cost:
            return self.data.get("total") or self.data.get("cost")
        return None


@dataclass
class RawLogEntry:
    """Represents a non-JSON log line."""

    raw: str

    @property
    def log_type(self) -> str:
        return "raw"


LogEntry = AgentLogEntry | RawLogEntry


def safe_string(s: str, max_length: int = 200) -> str:
    """
    Safely convert a string for logging, handling encoding issues.

    Args:
        s: Input string that might have encoding issues.
        max_length: Maximum length to display.

    Returns:
        A safe string for logging.
    """
    try:
        # Try to encode/decode to handle any weird characters
        safe = s.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
        if len(safe) > max_length:
            return safe[:max_length] + "..."
        return safe
    except Exception:
        return "<unparseable content>"


def parse_log_line(line: str) -> LogEntry:
    """
    Parse a raw log line from the agent.

    Attempts to parse the line as JSON. If successful and contains a 'type' field,
    returns an AgentLogEntry. Otherwise returns a RawLogEntry.

    This function is resilient to encoding issues and malformed JSON.

    Args:
        line: Raw log line string from the agent output.

    Returns:
        Either an AgentLogEntry (for valid JSON logs) or RawLogEntry (for plain text).

    Examples:
        >>> entry = parse_log_line('{"type": "step", "step": 1, "message": "Starting..."}')
        >>> entry.is_step
        True
        >>> entry.step_number
        1

        >>> entry = parse_log_line("Some plain text output")
        >>> entry.log_type
        'raw'
    """
    # Handle None or non-string input
    if not isinstance(line, str):
        try:
            line = str(line)
        except Exception:
            return RawLogEntry(raw="<non-string input>")

    # Safely strip the line
    try:
        stripped = line.strip()
    except Exception:
        return RawLogEntry(raw=safe_string(line))

    if not stripped:
        return RawLogEntry(raw=line)

    # Quick check - JSON must start with {
    if not stripped.startswith("{"):
        return RawLogEntry(raw=line)

    try:
        data = json.loads(stripped)

        if isinstance(data, dict) and "type" in data:
            return AgentLogEntry(
                log_type=str(data["type"]),
                data=data,
                raw=line,
            )

        # Valid JSON but not an agent log format
        return RawLogEntry(raw=line)

    except json.JSONDecodeError as e:
        # Log the error for debugging but don't crash
        logger.debug(f"JSON parse failed: {e}. Line: {safe_string(stripped, 100)}")
        return RawLogEntry(raw=line)
    except UnicodeDecodeError as e:
        # Handle encoding errors gracefully
        logger.debug(f"Unicode error: {e}. Line: {safe_string(stripped, 100)}")
        return RawLogEntry(raw=safe_string(line))
    except Exception as e:
        # Catch-all for any unexpected errors
        logger.warning(f"Unexpected parse error: {type(e).__name__}: {e}")
        return RawLogEntry(raw=safe_string(line))


def format_log_entry(entry: LogEntry) -> str:
    """
    Format a log entry for display.

    Args:
        entry: The log entry to format.

    Returns:
        A formatted string for terminal display.
    """
    try:
        if isinstance(entry, RawLogEntry):
            return entry.raw

        if entry.is_step:
            step_num = entry.step_number or "?"
            message = entry.message or "Processing..."
            return f"[Step {step_num}] {message}"

        if entry.is_cost:
            cost = entry.cost
            if cost is not None:
                return f"[Cost] ${cost:.4f}"
            return "[Cost] Unknown"

        if entry.is_result:
            message = entry.message or "Completed"
            return f"[Result] {message}"

        if entry.is_error:
            message = entry.message or "Unknown error"
            return f"[Error] {message}"

        # Generic structured log
        return f"[{entry.log_type}] {entry.message or json.dumps(entry.data)}"

    except Exception as e:
        logger.warning(f"Format error: {e}")
        return f"[Format Error] {safe_string(str(entry), 100)}"

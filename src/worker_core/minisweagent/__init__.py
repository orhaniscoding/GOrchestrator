"""
Mini-SWE-GOCore - Portable, headless-first agent framework.

This file provides:
- Portable path utilities (everything in .miniswe/ directory)
- Version numbering
- Auto-initialization on first run
- Protocols for the core components of mini-swe-agent.
"""

__version__ = "2.0.0"

import os
from pathlib import Path
from typing import Any, Protocol, Optional

import dotenv

from minisweagent.utils.log import logger

package_dir = Path(__file__).resolve().parent

# === AGENT HOME DIRECTORY ===
# All agent files are contained in a single .miniswe directory
AGENT_DIR_NAME = ".miniswe"

_workdir_cache: Optional[Path] = None


def get_workdir() -> Path:
    """Get the working directory (project root).

    Priority:
    1. MINI_WORKDIR environment variable
    2. Current working directory

    The agent home (.miniswe/) is created inside this directory.
    """
    global _workdir_cache
    if _workdir_cache is None:
        _workdir_cache = Path(os.getenv("MINI_WORKDIR", ".")).resolve()
    return _workdir_cache


def set_workdir(path: Path | str) -> None:
    """Set the working directory programmatically."""
    global _workdir_cache
    _workdir_cache = Path(path).resolve()
    os.environ["MINI_WORKDIR"] = str(_workdir_cache)


def get_agent_dir() -> Path:
    """Get the agent home directory: {workdir}/.miniswe/

    This is the single directory containing all agent-related files.
    Created automatically if it doesn't exist.
    """
    agent_dir = get_workdir() / AGENT_DIR_NAME
    agent_dir.mkdir(parents=True, exist_ok=True)
    return agent_dir


def get_config_dir() -> Path:
    """Get configs directory: {workdir}/.miniswe/configs/"""
    config_dir = get_agent_dir() / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_data_dir() -> Path:
    """Get data directory: {workdir}/.miniswe/data/"""
    data_dir = get_agent_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_logs_dir() -> Path:
    """Get logs directory: {workdir}/.miniswe/logs/"""
    logs_dir = get_agent_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_config_file() -> Path:
    """Get the .env config file path: {workdir}/.miniswe/configs/.env"""
    return get_config_dir() / ".env"


# === AUTO-INITIALIZATION ===
# Default config that gets created on first run

DEFAULT_LIVE_CONFIG = """\
# Mini-SWE-GOCore Live Profile
# ==========================
# Auto-generated on first run. Edit as needed.
#
# Usage:
#   mini --profile live --task "Fix the bug"
#   mini --headless --profile live --task "Refactor code"
#
# Environment Variables:
#   MINI_API_BASE    - Custom API endpoint
#   MINI_API_KEY     - API key for proxy
#   MINI_API_TIMEOUT - Request timeout (seconds)

model:
  model_class: litellm
  model_name: "gpt-4o"
  cost_tracking: "ignore_errors"
  model_kwargs:
    temperature: 0.0
    max_tokens: 4096

environment:
  cwd: "."
  timeout: 120

agent:
  mode: "confirm"
  step_limit: 50
  cost_limit: 5.0
  confirm_exit: true

headless:
  include_timestamps: true
  max_output_length: 10000
"""

DEFAULT_GITIGNORE = """\
# Mini-SWE-GOCore agent files
# Keep configs/ for version control, ignore data and logs

data/
logs/
*.log
"""

_initialized = False


def initialize_agent_dir() -> bool:
    """Initialize the .miniswe directory structure on first run.

    Creates:
    - .miniswe/configs/live.yaml (default profile)
    - .miniswe/configs/.gitignore
    - .miniswe/data/
    - .miniswe/logs/

    Returns True if initialization was performed, False if already exists.
    """
    global _initialized
    if _initialized:
        return False

    config_dir = get_config_dir()
    live_config = config_dir / "live.yaml"
    gitignore = get_agent_dir() / ".gitignore"

    created = False

    # Create default live.yaml if not exists
    if not live_config.exists():
        live_config.write_text(DEFAULT_LIVE_CONFIG)
        created = True

    # Create .gitignore if not exists
    if not gitignore.exists():
        gitignore.write_text(DEFAULT_GITIGNORE)
        created = True

    # Ensure data and logs dirs exist
    get_data_dir()
    get_logs_dir()

    _initialized = True
    return created


# === HEADLESS MODE ===
def is_headless() -> bool:
    """Check if running in headless mode (no TUI)."""
    return os.getenv("MINI_HEADLESS", "false").lower() in ("true", "1", "yes")


def set_headless(value: bool) -> None:
    """Set headless mode programmatically."""
    os.environ["MINI_HEADLESS"] = "true" if value else "false"


# === ENVIRONMENT LOADING ===
def load_env() -> None:
    """Load environment from {workdir}/.miniswe/configs/.env if exists."""
    env_file = get_config_file()
    if env_file.exists():
        dotenv.load_dotenv(dotenv_path=env_file)


# === STARTUP BANNER ===
_startup_shown = False


def _show_startup_banner() -> None:
    """Show startup banner (only in interactive mode)."""
    global _startup_shown
    if _startup_shown:
        return
    _startup_shown = True

    if is_headless():
        return

    if os.getenv("MINI_SILENT_STARTUP") or os.getenv("MSWEA_SILENT_STARTUP"):
        return

    try:
        from rich.console import Console
        console = Console()
        console.print(
            f"[bold green]Mini-SWE-GOCore[/bold green] v{__version__} | "
            f"Agent dir: [cyan]{get_agent_dir()}[/cyan]"
        )
    except ImportError:
        pass


# Load environment on import
load_env()


# === BACKWARD COMPATIBILITY ===
def _get_legacy_global_config_dir() -> Path:
    """Deprecated: Use get_config_dir() instead."""
    import warnings
    warnings.warn(
        "global_config_dir is deprecated. Use get_config_dir() for portable paths.",
        DeprecationWarning,
        stacklevel=3
    )
    return get_config_dir()


def _get_legacy_global_config_file() -> Path:
    """Deprecated: Use get_config_file() instead."""
    import warnings
    warnings.warn(
        "global_config_file is deprecated. Use get_config_file() for portable paths.",
        DeprecationWarning,
        stacklevel=3
    )
    return get_config_file()


class _LegacyPath:
    def __init__(self, getter):
        self._getter = getter

    def __fspath__(self):
        return str(self._getter())

    def __str__(self):
        return str(self._getter())

    def __truediv__(self, other):
        return self._getter() / other

    def __repr__(self):
        return repr(self._getter())


global_config_dir = _LegacyPath(_get_legacy_global_config_dir)
global_config_file = _LegacyPath(_get_legacy_global_config_file)


# === Protocols ===

class Model(Protocol):
    """Protocol for language models."""
    config: Any
    cost: float
    n_calls: int

    def query(self, messages: list[dict[str, str]], **kwargs) -> dict: ...
    def get_template_vars(self) -> dict[str, Any]: ...


class Environment(Protocol):
    """Protocol for execution environments."""
    config: Any

    def execute(self, command: str, cwd: str = "") -> dict[str, str]: ...
    def get_template_vars(self) -> dict[str, Any]: ...


class Agent(Protocol):
    """Protocol for agents."""
    model: Model
    env: Environment
    messages: list[dict[str, str]]
    config: Any

    def run(self, task: str, **kwargs) -> tuple[str, str]: ...


class OutputHandler(Protocol):
    """Protocol for output handlers (JSON, Rich, etc.)."""

    def emit(self, event_type: str, data: dict) -> None: ...
    def flush(self) -> None: ...


__all__ = [
    # Protocols
    "Agent",
    "Model",
    "Environment",
    "OutputHandler",
    # Path utilities
    "package_dir",
    "AGENT_DIR_NAME",
    "get_workdir",
    "set_workdir",
    "get_agent_dir",
    "get_config_dir",
    "get_data_dir",
    "get_logs_dir",
    "get_config_file",
    # Initialization
    "initialize_agent_dir",
    # Mode utilities
    "is_headless",
    "set_headless",
    "load_env",
    # Version
    "__version__",
    # Deprecated (backward compat)
    "global_config_file",
    "global_config_dir",
    # Logging
    "logger",
]

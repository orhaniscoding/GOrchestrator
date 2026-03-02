#!/usr/bin/env python3

"""Run Mini-SWE-GOCore agent.

Modes:
- Interactive (default): Rich TUI with prompt_toolkit
- Headless (--headless): JSON Lines output for automation

Portable paths (all inside .miniswe/):
- Configs: .miniswe/configs/
- Data: .miniswe/data/
- Logs: .miniswe/logs/

Usage:
    mini --profile live --task "Fix the bug"
    mini --headless --task "Refactor code" > output.jsonl
    mini --workdir ./project --profile dev
"""

import traceback
from pathlib import Path
from typing import Any, Optional

import typer
import yaml

from minisweagent import (
    __version__,
    get_data_dir,
    initialize_agent_dir,
    is_headless,
    set_headless,
    set_workdir,
    _show_startup_banner,
)
from minisweagent.config import builtin_config_dir, get_config_path, get_profile_path, SAFE_MODE_CONFIG
from minisweagent.environments.local import LocalEnvironment
from minisweagent.models import get_model
from minisweagent.run.utils.save import save_traj
from minisweagent.utils.log import logger

# Disable shell completion commands (--install-completion, --show-completion)
app = typer.Typer(rich_markup_mode="rich", add_completion=False)

_HELP_TEXT = f"""Run Mini-SWE-GOCore agent (v{__version__}).

[bold]Modes:[/bold]
  [green]mini[/green]              Interactive mode (Rich TUI)
  [green]mini --headless[/green]   Headless mode (JSON Lines to stdout)

[bold]Profiles:[/bold]
  [green]mini --profile live[/green]    Load .miniswe/configs/live.yaml
  [green]mini --profile dev[/green]     Load .miniswe/configs/dev.yaml

[bold]Portable Paths:[/bold]
  All paths inside .miniswe/ (relative to --workdir)
  Configs: .miniswe/configs/
  Data:    .miniswe/data/
  Logs:    .miniswe/logs/

[bold]Custom Proxy:[/bold]
  MINI_API_BASE=http://localhost:8080 mini --headless --task "Hello"
"""


def _get_task_interactive() -> str:
    """Prompt for task in interactive mode."""
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.shortcuts import PromptSession
    from rich.console import Console

    console = Console(highlight=False)
    history_file = get_data_dir() / "task_history.txt"
    prompt_session = PromptSession(history=FileHistory(str(history_file)))

    console.print("[bold yellow]What do you want to do?")
    task = prompt_session.prompt(
        "",
        multiline=True,
        bottom_toolbar=HTML(
            "Submit task: <b fg='yellow' bg='black'>Esc+Enter</b> | "
            "Navigate history: <b fg='yellow' bg='black'>Arrow Up/Down</b> | "
            "Search history: <b fg='yellow' bg='black'>Ctrl+R</b>"
        ),
    )
    console.print("[bold green]Got that, thanks![/bold green]")
    return task


# fmt: off
@app.command(help=_HELP_TEXT)
def main(
    # === CORE ARGUMENTS ===
    profile: Optional[str] = typer.Option(
        None, "-p", "--profile",
        help="Profile name (loads .miniswe/configs/{profile}.yaml)"
    ),
    workdir: Path = typer.Option(
        Path("."), "-w", "--workdir",
        help="Working directory (project root)"
    ),
    headless: bool = typer.Option(
        False, "--headless",
        help="Headless mode: JSON Lines output, no TUI"
    ),
    task: Optional[str] = typer.Option(
        None, "-t", "--task",
        help="Task/problem statement",
        show_default=False
    ),

    # === OPTIONAL OVERRIDES ===
    model_name: Optional[str] = typer.Option(
        None, "-m", "--model",
        help="Model override (e.g., 'gpt-4o', 'claude-3-opus')"
    ),
    yolo: bool = typer.Option(
        False, "-y", "--yolo",
        help="Run without confirmation prompts"
    ),
    cost_limit: Optional[float] = typer.Option(
        None, "-l", "--cost-limit",
        help="Cost limit in USD (0 to disable)"
    ),
    config_spec: Optional[Path] = typer.Option(
        None, "-c", "--config",
        help="Direct path to config file (overrides --profile)"
    ),
    output: Optional[Path] = typer.Option(
        None, "-o", "--output",
        help="Output trajectory file path"
    ),
) -> Any:
    # fmt: on

    # === SET WORKDIR FIRST ===
    set_workdir(workdir)

    # === SET HEADLESS MODE ===
    if headless:
        set_headless(True)

    # === AUTO-INITIALIZE .miniswe DIRECTORY ===
    initialized = initialize_agent_dir()

    if initialized and not is_headless():
        from rich.console import Console
        Console().print("[dim]Initialized new agent workspace in .miniswe/[/dim]")

    # === SHOW STARTUP BANNER (interactive only) ===
    if not is_headless():
        _show_startup_banner()

    # === RESOLVE CONFIG ===
    config_path = None
    config = None

    if config_spec:
        try:
            config_path = get_config_path(config_spec, workdir=workdir)
        except FileNotFoundError as e:
            if is_headless():
                import json
                import sys
                sys.stdout.write(json.dumps({"type": "error", "data": {"error": str(e)}}) + "\n")
                sys.stdout.flush()
            else:
                from rich.console import Console
                Console().print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(1)
    elif profile:
        try:
            config_path = get_profile_path(profile, workdir=workdir)
        except FileNotFoundError:
            if not is_headless():
                from rich.console import Console
                Console().print(
                    f"[yellow]Profile '{profile}' not found in .miniswe/configs/. Using safe mode defaults.[/yellow]"
                )
            config = SAFE_MODE_CONFIG.copy()
    else:
        try:
            config_path = get_profile_path("default", workdir=workdir)
        except FileNotFoundError:
            try:
                config_path = builtin_config_dir / "mini.yaml"
            except FileNotFoundError:
                config = SAFE_MODE_CONFIG.copy()

    # Load config from path
    if config is None and config_path:
        if not is_headless():
            from rich.console import Console
            Console(highlight=False).print(
                f"Loading config from [bold green]'{config_path}'[/bold green]"
            )
        config = yaml.safe_load(config_path.read_text()) or {}

    if config is None:
        config = SAFE_MODE_CONFIG.copy()

    # === SET OUTPUT PATH ===
    if output is None:
        output = get_data_dir() / "last_run.traj.json"

    # === GET TASK ===
    if not task:
        if is_headless():
            import json
            import sys
            sys.stdout.write(json.dumps({
                "type": "error",
                "data": {"error": "--task is required in headless mode"}
            }) + "\n")
            sys.stdout.flush()
            raise typer.Exit(1)
        task = _get_task_interactive()

    # === APPLY CLI OVERRIDES ===
    if yolo:
        config.setdefault("agent", {})["mode"] = "yolo"
    if cost_limit is not None:
        config.setdefault("agent", {})["cost_limit"] = cost_limit

    # === CREATE MODEL & ENVIRONMENT ===
    model = get_model(model_name, config.get("model", {}))
    env = LocalEnvironment(**config.get("environment", {}))

    # === SELECT AGENT CLASS ===
    if is_headless():
        from minisweagent.agents.headless import HeadlessAgent
        agent_class = HeadlessAgent
    else:
        from minisweagent.agents.interactive import InteractiveAgent
        agent_class = InteractiveAgent

    # === RUN AGENT ===
    agent = agent_class(model, env, **config.get("agent", {}))
    exit_status, result, extra_info = None, None, None

    try:
        exit_status, result = agent.run(task)
    except Exception as e:
        logger.error(f"Error running agent: {e}", exc_info=True)
        exit_status, result = type(e).__name__, str(e)
        extra_info = {"traceback": traceback.format_exc()}
    finally:
        save_traj(agent, output, exit_status=exit_status, result=result, extra_info=extra_info)

    return agent


if __name__ == "__main__":
    app()

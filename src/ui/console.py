"""
Console UI - Rich-based terminal interface for GOrchestrator.
Provides beautiful formatting for Manager, Worker, and User interactions.
Uses prompt_toolkit for advanced input (history, multi-line paste, autocomplete).
"""

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import NestedCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings


class SafeFileHistory(FileHistory):
    """FileHistory subclass that sanitizes surrogates and filters sensitive commands."""

    # Commands that may contain API keys - don't persist these
    _SENSITIVE_PATTERNS = (
        "/worker api", "/manager api", "/manager set api", "/config set", "/submanager api",
        "/manager llm add", "/manager llm set", "/submanager llm",
    )

    def store_string(self, string: str) -> None:
        safe = string.encode("utf-8", errors="replace").decode("utf-8")
        # Don't store commands that may contain API keys
        stripped = safe.strip().lower()
        for pattern in self._SENSITIVE_PATTERNS:
            if stripped.startswith(pattern):
                return  # Skip storing this command
        super().store_string(safe)
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Prompt
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from ..utils.parser import AgentLogEntry, LogEntry, RawLogEntry


def _build_completer_from_tree(tree: dict[str, list[str] | None]) -> NestedCompleter:
    """Build a NestedCompleter from the SLASH_COMMAND_TREE registry."""
    nested: dict[str, NestedCompleter | None] = {}
    for cmd, subs in tree.items():
        if subs:
            nested[cmd] = NestedCompleter.from_nested_dict(
                {s: None for s in subs}
            )
        else:
            nested[cmd] = None
    return NestedCompleter.from_nested_dict(nested)

# Custom theme for GOrchestrator
GORCHESTRATOR_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "step": "bold blue",
    "cost": "magenta",
    # Role-specific styles
    "user": "bold green",
    "manager": "bold cyan",
    "worker": "dim white",
    "thinking": "italic cyan",
    # Panel styles
    "manager.border": "cyan",
    "worker.border": "dim white",
    "user.border": "green",
    "header": "bold white on blue",
})


class ConsoleUI:
    """
    Rich-based console interface for GOrchestrator.
    Provides formatted output for Manager, Worker, and User interactions.
    """

    # History file path (project-level)
    _HISTORY_DIR = Path(__file__).resolve().parent.parent.parent / ".gorchestrator"

    def __init__(self, verbose_worker: bool = False):
        """
        Initialize the console UI.

        Args:
            verbose_worker: If True, show detailed Worker output.
        """
        self.console = Console(theme=GORCHESTRATOR_THEME)
        self.verbose_worker = verbose_worker
        self._current_step = 0
        self._worker_lines = []

        # Setup prompt_toolkit session with persistent history and autocomplete
        self._prompt_session: PromptSession | None = None
        try:
            self._HISTORY_DIR.mkdir(parents=True, exist_ok=True)
            history_file = self._HISTORY_DIR / "input_history.txt"

            # Build nested completer from the command registry (single source of truth)
            from ..commands.completer import TabCompleter
            tab_completer = TabCompleter()
            self._completer = _build_completer_from_tree(tab_completer.get_completer_tree())

            # Key bindings: Enter sends, Ctrl+J inserts newline
            kb = KeyBindings()

            @kb.add("enter")
            def _handle_enter(event):
                event.current_buffer.validate_and_handle()

            @kb.add("c-j")  # Ctrl+J = newline (works on all terminals)
            def _handle_newline(event):
                event.current_buffer.insert_text("\n")

            self._prompt_session = PromptSession(
                history=SafeFileHistory(str(history_file)),
                auto_suggest=AutoSuggestFromHistory(),
                completer=self._completer,
                complete_while_typing=True,
                multiline=True,
                key_bindings=kb,
                enable_open_in_editor=False,
            )
        except Exception:
            # Fallback: no prompt_toolkit (e.g. no console in test/CI)
            self._prompt_session = None

    def print_header(self):
        """Display the application header."""
        header = Text()
        header.append("  GOrchestrator  ", style="bold white on blue")
        header.append(" - ", style="dim")
        header.append("Intelligent AI Agent Manager", style="italic")

        self.console.print()
        self.console.print(Panel(header, border_style="blue", padding=(0, 2)))
        self.console.print()

    def print_dashboard(self, info: dict):
        """Display a rich startup/status dashboard.

        Args:
            info: Dict with keys: session_name, session_status, msg_count,
                  manager_model, api_base, workers (list of dicts with
                  name/model/profile/active/primary/api_base),
                  sub_managers (list of dicts with name/profile/model/active/description),
                  active_team (dict with name/main_manager_profile/sub_manager_names or None),
                  mode, confirm.
        """
        parts: list[str] = []

        # Session line
        session = info.get("session_name", "")
        status = info.get("session_status", "new")
        msg_count = info.get("msg_count", 0)
        if status == "restored":
            parts.append(f"  [bold]Session:[/bold] {session} [dim](restored, {msg_count} messages)[/dim]")
        else:
            parts.append(f"  [bold]Session:[/bold] {session} [dim](new)[/dim]")

        # Manager line
        manager_model = info.get("manager_model", "?")
        api_base = info.get("api_base", "?")
        parts.append(f"  [bold]Manager:[/bold] [cyan]{manager_model}[/cyan] [dim]@ {api_base}[/dim]")

        # Active team
        active_team = info.get("active_team")
        if active_team:
            parts.append("")
            parts.append(f"  [bold]Active Team:[/bold] [yellow]{active_team['name']}[/yellow]")

        # Sub-managers
        sub_managers = info.get("sub_managers", [])
        if sub_managers:
            parts.append("")
            parts.append("  [bold]Sub-Managers (Advisors):[/bold]")
            for sm in sub_managers:
                marker = "[yellow]●[/yellow]" if sm.get("active") else "[dim]○[/dim]"
                desc = f" - {sm['description']}" if sm.get("description") else ""
                parts.append(
                    f"    {marker} [yellow]{sm['name']}[/yellow]"
                    f"  [dim]({sm['model']}, {sm['profile']}){desc}[/dim]"
                )

        # Parallel LLMs (Manager)
        parallel_llms = info.get("parallel_llms", [])
        if parallel_llms:
            parts.append("")
            parts.append("  [bold]Parallel LLMs (Manager):[/bold]")
            for llm in parallel_llms:
                parts.append(
                    f"    [magenta]●[/magenta] [magenta]{llm['name']}[/magenta]"
                    f"  [dim]({llm['model']})[/dim]"
                )

        # Workers
        workers = info.get("workers", [])
        if workers:
            parts.append("")
            parts.append("  [bold]Workers:[/bold]")
            for w in workers:
                marker = "[green]●[/green]" if w.get("active") else "[dim]○[/dim]"
                primary_tag = " [yellow]\\[primary][/yellow]" if w.get("primary") else ""
                api_tag = f" [dim]@ {w['api_base']}[/dim]" if w.get("api_base") else ""
                parts.append(
                    f"    {marker} [green]{w['name']}[/green]"
                    f"  [dim]({w['model']}, {w['profile']})[/dim]"
                    f"{primary_tag}{api_tag}"
                )

        # Mode line
        mode = info.get("mode", "Quiet")
        confirm = info.get("confirm", "OFF")
        parts.append("")
        parts.append(f"  [dim]Mode: {mode} | Confirm: {confirm}[/dim]")

        body = "\n".join(parts)
        self.console.print()
        self.console.print(
            Panel(body, title="[bold blue]GOrchestrator[/bold blue]",
                  border_style="blue", padding=(0, 1)),
        )
        self.console.print()

    def print_settings(self, settings: dict[str, str]):
        """Display current settings in a table."""
        table = Table(title="Configuration", show_header=True, header_style="bold cyan")
        table.add_column("Setting", style="dim")
        table.add_column("Value", style="green")

        for key, value in settings.items():
            # Mask sensitive values regardless of length
            if "KEY" in key.upper() and str(value) and str(value) != "N/A":
                val = str(value)
                display_value = f"****...{val[-4:]}" if len(val) > 4 else "****"
            else:
                display_value = str(value)
            table.add_row(key, display_value)

        self.console.print(table)
        self.console.print()

    # ================================================================
    # USER Display Methods
    # ================================================================

    def display_user_message(self, message: str):
        """Display a user message with formatting."""
        self.console.print()
        panel = Panel(
            Text(message, style="user"),
            title="[bold green]👤 You[/bold green]",
            border_style="green",
            padding=(0, 1),
        )
        self.console.print(panel)

    # ================================================================
    # MANAGER Display Methods
    # ================================================================

    def display_manager_thinking(self, text: str):
        """Display Manager thinking/status."""
        self.console.print(f"  [thinking]🧠 {text}[/thinking]")

    def display_manager_message(self, content: str):
        """Display Manager's response."""
        self.console.print()

        # Render markdown content
        try:
            md = Markdown(content)
            panel = Panel(
                md,
                title="[bold cyan]🧠 Manager[/bold cyan]",
                border_style="cyan",
                padding=(0, 1),
            )
        except Exception:
            # Fallback to plain text
            panel = Panel(
                Text(content, style="manager"),
                title="[bold cyan]🧠 Manager[/bold cyan]",
                border_style="cyan",
                padding=(0, 1),
            )

        self.console.print(panel)

    def display_manager_tool_call(self, tool_name: str, description: str):
        """Display when Manager decides to use a tool."""
        self.console.print()
        text = Text()
        text.append(f"🔧 Calling tool: ", style="dim")
        text.append(tool_name, style="bold cyan")
        if description:
            text.append(f"\n   Task: {description[:100]}...", style="dim")
        self.console.print(text)

    # ================================================================
    # SUB-MANAGER Display Methods
    # ================================================================

    def display_sub_manager_response(self, sm_response):
        """Display a sub-manager's advisory response.

        Args:
            sm_response: SubManagerResponse object with name, content, model, duration_seconds, error.
        """
        self.console.print()

        if sm_response.error:
            panel = Panel(
                Text(f"Error: {sm_response.error}", style="error"),
                title=f"[bold yellow]🎯 Advisor: {sm_response.name}[/bold yellow]",
                border_style="red",
                padding=(0, 1),
            )
        else:
            # Build subtitle with metadata
            subtitle = f"[dim]{sm_response.model} | {sm_response.duration_seconds:.1f}s[/dim]"

            try:
                md = Markdown(sm_response.content)
                panel = Panel(
                    md,
                    title=f"[bold yellow]🎯 Advisor: {sm_response.name}[/bold yellow]",
                    subtitle=subtitle,
                    border_style="yellow",
                    padding=(0, 1),
                )
            except Exception:
                panel = Panel(
                    Text(sm_response.content),
                    title=f"[bold yellow]🎯 Advisor: {sm_response.name}[/bold yellow]",
                    subtitle=subtitle,
                    border_style="yellow",
                    padding=(0, 1),
                )

        self.console.print(panel)

    # ================================================================
    # PARALLEL LLM POOL Display Methods
    # ================================================================

    def display_llm_pool_response(self, llm_response):
        """Display a parallel LLM pool response.

        Args:
            llm_response: LLMResponse object with name, content, model, duration_seconds, error.
        """
        self.console.print()

        if llm_response.error:
            panel = Panel(
                Text(f"Error: {llm_response.error}", style="error"),
                title=f"[bold magenta]🔮 Parallel LLM: {llm_response.name}[/bold magenta]",
                border_style="red",
                padding=(0, 1),
            )
        else:
            subtitle = f"[dim]{llm_response.model} | {llm_response.duration_seconds:.1f}s[/dim]"

            try:
                md = Markdown(llm_response.content)
                panel = Panel(
                    md,
                    title=f"[bold magenta]🔮 Parallel LLM: {llm_response.name}[/bold magenta]",
                    subtitle=subtitle,
                    border_style="magenta",
                    padding=(0, 1),
                )
            except Exception:
                panel = Panel(
                    Text(llm_response.content),
                    title=f"[bold magenta]🔮 Parallel LLM: {llm_response.name}[/bold magenta]",
                    subtitle=subtitle,
                    border_style="magenta",
                    padding=(0, 1),
                )

        self.console.print(panel)

    # ================================================================
    # WORKER Display Methods
    # ================================================================

    def start_worker_section(self):
        """Start a new Worker output section."""
        self._worker_lines = []
        self._current_step = 0
        self.console.print()
        self.console.print(Rule("[dim]👷 Worker Execution[/dim]", style="dim"))

    def display_worker_step(self, entry: LogEntry, worker_name: str = "worker"):
        """
        Display a Worker step/output line.

        Args:
            entry: Parsed log entry from the Worker.
            worker_name: Name of the worker producing this output.
        """
        # Store for summary
        if isinstance(entry, AgentLogEntry):
            self._worker_lines.append(entry)

        # In verbose mode, show everything
        if self.verbose_worker:
            self._display_worker_step_verbose(entry, worker_name)
        else:
            self._display_worker_step_compact(entry, worker_name)

    def _display_worker_step_verbose(self, entry: LogEntry, worker_name: str = "worker"):
        """Display Worker step in verbose mode."""
        tag = f"[dim][{worker_name}][/dim] " if worker_name != "worker" else "    "
        if isinstance(entry, RawLogEntry):
            if entry.raw.strip():
                self.console.print(f"{tag}[worker]{entry.raw}[/worker]")
            return

        if entry.is_step:
            self._current_step = entry.step_number or self._current_step + 1
            message = entry.message or "Processing..."
            self.console.print(f"{tag}[dim][Step {self._current_step}][/dim] {message}")

        elif entry.is_cost:
            cost = entry.cost
            if cost is not None:
                self.console.print(f"{tag}[cost]$ {cost:.4f}[/cost]")

        elif entry.is_error:
            message = entry.message or "Unknown error"
            self.console.print(f"{tag}[error]{message}[/error]")

        elif entry.is_result:
            message = entry.message or "Done"
            self.console.print(f"{tag}[success]{message}[/success]")

        else:
            self.console.print(f"{tag}[dim][{entry.log_type}] {entry.message or ''}[/dim]")

    def _display_worker_step_compact(self, entry: LogEntry, worker_name: str = "worker"):
        """Display Worker step in compact mode (minimal output)."""
        tag = f"[{worker_name}] " if worker_name != "worker" else ""
        if isinstance(entry, RawLogEntry):
            return

        if entry.is_step:
            self._current_step = entry.step_number or self._current_step + 1
            self.console.print(f"    [dim]{tag}Step {self._current_step}...[/dim]", end="\r")

        elif entry.is_error:
            message = entry.message or "Error occurred"
            self.console.print(f"    [error]{tag}{message}[/error]")

    def display_worker_result(self, result: Any, title: str = "Worker Result"):
        """Display the Worker's final result."""
        from ..core.worker import TaskResult, TaskStatus

        self.console.print()  # Clear the step line

        if not isinstance(result, TaskResult):
            self.console.print(Panel(str(result), title=title, border_style="dim"))
            return

        # Build compact result summary
        content = Text()

        if result.is_success:
            content.append("✓ SUCCESS", style="success")
        else:
            content.append("✗ FAILED", style="error")

        content.append(f"  |  Steps: {result.step_count}")
        content.append(f"  |  Cost: ${result.total_cost:.4f}")
        content.append(f"  |  Time: {result.duration_seconds:.1f}s")

        if result.error_message:
            content.append(f"\n[error]Error: {result.error_message}[/error]")

        border_style = "green" if result.is_success else "red"
        self.console.print(Panel(
            content,
            title="[dim]👷 Worker Result[/dim]",
            border_style=border_style,
            padding=(0, 1),
        ))

    def end_worker_section(self):
        """End Worker output section."""
        self.console.print(Rule(style="dim"))

    # ================================================================
    # Input Methods
    # ================================================================

    def get_user_input(self, prompt: str = "You", default: str = "") -> str:
        """
        Get input from user using prompt_toolkit.
        Supports: arrow-key history, multi-line paste, slash-command autocomplete.
        Alt+Enter inserts a new line, Enter sends the message.
        Falls back to rich.Prompt if prompt_toolkit is unavailable.
        """
        self.console.print()
        if self._prompt_session is not None:
            try:
                result = self._prompt_session.prompt(
                    HTML(
                        f"<ansigreen><b>{prompt}</b></ansigreen>"
                        " <ansigray>(Ctrl+J: new line)</ansigray>: "
                    ),
                    default=default,
                )
                # Sanitize surrogate characters from Windows clipboard
                result = result.encode("utf-8", errors="replace").decode("utf-8")
                return result
            except KeyboardInterrupt:
                raise
            except EOFError:
                raise
        # Fallback to rich prompt
        styled_prompt = f"[bold green]{prompt}[/bold green]"
        return Prompt.ask(styled_prompt, default=default, console=self.console)

    def get_feedback(self) -> tuple[bool, str]:
        """Ask user for approval or critique."""
        self.console.print()
        self.console.print(Rule("Feedback", style="dim"))
        self.console.print("[dim]Enter 'ok' to approve, or type feedback to critique:[/dim]")

        response = self.get_user_input("Feedback", default="ok")
        response_lower = response.lower().strip()

        if response_lower in ("ok", "approve", "yes", "y", "accept", "done", ""):
            return True, ""
        else:
            return False, response

    # ================================================================
    # Spinner/Progress Methods
    # ================================================================

    @contextmanager
    def spinner(self, text: str = "Working..."):
        """Show a loading spinner."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True,
        ) as progress:
            task = progress.add_task(text, total=None)
            yield progress

    @contextmanager
    def manager_thinking_spinner(self):
        """Show spinner for Manager thinking."""
        with self.spinner("🧠 Manager is thinking..."):
            yield

    @contextmanager
    def worker_progress(self):
        """Show progress bar for Worker execution."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[dim]👷 Worker executing...[/dim]"),
            BarColumn(bar_width=20),
            console=self.console,
            transient=True,
        ) as progress:
            task = progress.add_task("", total=None)
            yield progress

    # ================================================================
    # Utility Methods
    # ================================================================

    def print_separator(self, title: str = ""):
        """Print a horizontal rule/separator."""
        self.console.print()
        self.console.print(Rule(title, style="dim"))
        self.console.print()

    def print_error(self, message: str):
        """Print an error message."""
        self.console.print(f"[error]❌ Error: {message}[/error]")

    def print_success(self, message: str):
        """Print a success message."""
        self.console.print(f"[success]✓ {message}[/success]")

    def print_info(self, message: str):
        """Print an info message."""
        self.console.print(f"[info]ℹ {message}[/info]")

    def print_warning(self, message: str):
        """Print a warning message."""
        self.console.print(f"[warning]⚠ Warning: {message}[/warning]")

    def show_history(self, history: list[dict]):
        """Display conversation history."""
        if not history:
            self.console.print("[dim]No history yet.[/dim]")
            return

        table = Table(title="Session History", show_header=True, header_style="bold")
        table.add_column("#", style="dim", width=3)
        table.add_column("Role", width=10)
        table.add_column("Content", overflow="fold")
        table.add_column("Tool?", width=5)

        for i, entry in enumerate(history, 1):
            role = entry.get("role", "unknown")
            content = entry.get("content", "")[:60]
            if len(entry.get("content", "")) > 60:
                content += "..."
            has_tool = "✓" if entry.get("has_tool_calls") else ""

            # Role styling
            if role == "user":
                role_display = "[user]👤 user[/user]"
            elif role == "assistant":
                role_display = "[manager]🧠 manager[/manager]"
            elif role == "tool":
                role_display = "[worker]👷 worker[/worker]"
            else:
                role_display = role

            table.add_row(str(i), role_display, content, has_tool)

        self.console.print(table)

    def show_full_history(self, history: list[dict]):
        """Display full conversation history without truncation."""
        if not history:
            self.console.print("[dim]No history yet.[/dim]")
            return

        for i, entry in enumerate(history, 1):
            role = entry.get("role", "unknown")
            content = entry.get("content", "")
            timestamp = entry.get("timestamp", "")

            if role == "user":
                title = f"[bold green]#{i} 👤 You[/bold green]"
                border = "green"
            elif role == "assistant":
                title = f"[bold cyan]#{i} 🧠 Manager[/bold cyan]"
                border = "cyan"
            elif role == "tool":
                title = f"[dim]#{i} 👷 Worker Result[/dim]"
                border = "dim"
            else:
                title = f"#{i} {role}"
                border = "dim"

            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    title += f"  [dim]{dt.strftime('%H:%M:%S')}[/dim]"
                except Exception:
                    pass

            try:
                body = Markdown(content) if role == "assistant" else Text(content)
            except Exception:
                body = Text(content)

            self.console.print(Panel(body, title=title, border_style=border, padding=(0, 1)))

    def confirm(self, message: str, default: bool = False) -> bool:
        """Ask for yes/no confirmation."""
        from rich.prompt import Confirm
        return Confirm.ask(message, default=default, console=self.console)

    def clear(self):
        """Clear the console."""
        self.console.clear()

    # Legacy method for backward compatibility
    def display_step(self, entry: LogEntry):
        """Display a step (legacy, maps to Worker step)."""
        self.display_worker_step(entry)

    def display_result(self, result: Any, title: str = "Result"):
        """Display a result (legacy, maps to Worker result)."""
        self.display_worker_result(result, title)

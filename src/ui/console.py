"""
Console UI - Rich-based terminal interface for GOrchestrator.
Provides beautiful formatting for Manager, Worker, and User interactions.
"""

from contextlib import contextmanager
from typing import Any

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

    def print_header(self):
        """Display the application header."""
        header = Text()
        header.append("  GOrchestrator  ", style="bold white on blue")
        header.append(" - ", style="dim")
        header.append("Intelligent AI Agent Manager", style="italic")

        self.console.print()
        self.console.print(Panel(header, border_style="blue", padding=(0, 2)))
        self.console.print()

    def print_settings(self, settings: dict[str, str]):
        """Display current settings in a table."""
        table = Table(title="Configuration", show_header=True, header_style="bold cyan")
        table.add_column("Setting", style="dim")
        table.add_column("Value", style="green")

        for key, value in settings.items():
            # Mask sensitive values
            if "KEY" in key.upper() and len(str(value)) > 10:
                display_value = str(value)[:10] + "..."
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
    # WORKER Display Methods
    # ================================================================

    def start_worker_section(self):
        """Start a new Worker output section."""
        self._worker_lines = []
        self._current_step = 0
        self.console.print()
        self.console.print(Rule("[dim]👷 Worker Execution[/dim]", style="dim"))

    def display_worker_step(self, entry: LogEntry):
        """
        Display a Worker step/output line.

        Args:
            entry: Parsed log entry from the Worker.
        """
        # Store for summary
        if isinstance(entry, AgentLogEntry):
            self._worker_lines.append(entry)

        # In verbose mode, show everything
        if self.verbose_worker:
            self._display_worker_step_verbose(entry)
        else:
            self._display_worker_step_compact(entry)

    def _display_worker_step_verbose(self, entry: LogEntry):
        """Display Worker step in verbose mode."""
        if isinstance(entry, RawLogEntry):
            if entry.raw.strip():
                self.console.print(f"    [worker]{entry.raw}[/worker]")
            return

        if entry.is_step:
            self._current_step = entry.step_number or self._current_step + 1
            message = entry.message or "Processing..."
            self.console.print(f"    [dim][Step {self._current_step}][/dim] {message}")

        elif entry.is_cost:
            cost = entry.cost
            if cost is not None:
                self.console.print(f"    [cost]💰 Cost: ${cost:.4f}[/cost]")

        elif entry.is_error:
            message = entry.message or "Unknown error"
            self.console.print(f"    [error]❌ {message}[/error]")

        elif entry.is_result:
            message = entry.message or "Done"
            self.console.print(f"    [success]✓ {message}[/success]")

        else:
            self.console.print(f"    [dim][{entry.log_type}] {entry.message or ''}[/dim]")

    def _display_worker_step_compact(self, entry: LogEntry):
        """Display Worker step in compact mode (minimal output)."""
        if isinstance(entry, RawLogEntry):
            return  # Skip raw output in compact mode

        if entry.is_step:
            self._current_step = entry.step_number or self._current_step + 1
            # Only show step number, not full message
            self.console.print(f"    [dim]Step {self._current_step}...[/dim]", end="\r")

        elif entry.is_error:
            message = entry.message or "Error occurred"
            self.console.print(f"    [error]❌ {message}[/error]")

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
        """Get input from user with nice formatting."""
        self.console.print()
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

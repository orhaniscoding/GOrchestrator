"""
Session Engine - Interactive session manager for GOrchestrator.
Manages the conversation loop between User, Manager Agent, and Worker Agent.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from ..ui.console import ConsoleUI
from ..utils.parser import parse_log_line
from .config import Settings, get_settings
from .manager import ManagerAgent, ManagerResponse
from .worker import AgentWorker, TaskResult, TaskStatus

logger = logging.getLogger(__name__)


class SessionMode(Enum):
    """Operating mode for the session."""
    AUTO = "auto"  # Manager runs autonomously
    VERBOSE = "verbose"  # Show detailed Worker output


class SessionEngine:
    """
    Interactive session manager for GOrchestrator.
    Orchestrates the conversation between User and Manager Agent,
    with the Manager delegating to Worker Agent as needed.
    """

    SESSIONS_DIR = Path(".gorchestrator/sessions")

    def __init__(
        self,
        settings: Settings | None = None,
    ):
        """
        Initialize the session engine.

        Args:
            settings: Application settings.
        """
        self.settings = settings or get_settings()
        self.ui = ConsoleUI(verbose_worker=self.settings.VERBOSE_WORKER)
        self.manager: ManagerAgent | None = None
        self.mode = SessionMode.AUTO
        self._running = False

        # Ensure sessions directory exists
        self._ensure_sessions_dir()

    def _ensure_sessions_dir(self):
        """Create the sessions directory if it doesn't exist."""
        self.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    def _init_manager(self):
        """Initialize the Manager Agent with UI callbacks."""
        def on_worker_output(line: str):
            entry = parse_log_line(line)
            self.ui.display_worker_step(entry)

        def on_thinking(text: str):
            self.ui.display_manager_thinking(text)

        self.manager = ManagerAgent(
            settings=self.settings,
            on_worker_output=on_worker_output,
            on_thinking=on_thinking,
        )

    def save_session(self, name: str = "latest_session") -> Path:
        """Save the current session to a JSON file."""
        self._ensure_sessions_dir()
        filepath = self.SESSIONS_DIR / f"{name}.json"

        session_data = {
            "version": "2.0",
            "saved_at": datetime.now().isoformat(),
            "mode": self.mode.value,
            "manager_history": self.manager.export_history() if self.manager else [],
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Session saved to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            raise

    def load_session(self, name: str = "latest_session") -> bool:
        """Load a session from a JSON file."""
        filepath = self.SESSIONS_DIR / f"{name}.json"

        if not filepath.exists():
            logger.warning(f"Session file not found: {filepath}")
            return False

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                session_data = json.load(f)

            # Ensure manager is initialized
            if not self.manager:
                self._init_manager()

            # Restore manager history
            if "manager_history" in session_data:
                self.manager.import_history(session_data["manager_history"])

            # Restore mode
            mode_str = session_data.get("mode", "auto")
            if mode_str == "verbose":
                self.mode = SessionMode.VERBOSE
                self.ui.verbose_worker = True

            logger.info(f"Session loaded from {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return False

    def list_sessions(self) -> list[str]:
        """List all available session files."""
        self._ensure_sessions_dir()
        return [f.stem for f in self.SESSIONS_DIR.glob("*.json")]

    def _auto_save(self):
        """Automatically save the current session."""
        try:
            self.save_session("latest_session")
        except Exception as e:
            logger.warning(f"Auto-save failed: {e}")

    def _handle_slash_command(self, command: str) -> bool:
        """Handle a slash command."""
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "/save":
            name = arg.strip() or "manual_save"
            try:
                path = self.save_session(name)
                self.ui.print_success(f"Session saved to: {path}")
            except Exception as e:
                self.ui.print_error(f"Failed to save: {e}")
            return True

        elif cmd == "/load":
            name = arg.strip() or "latest_session"
            if self.load_session(name):
                self.ui.print_success(f"Session '{name}' loaded")
                self.ui.print_info("Previous conversation context restored.")
            else:
                self.ui.print_error(f"Session '{name}' not found.")
                available = self.list_sessions()
                if available:
                    self.ui.print_info(f"Available: {', '.join(available)}")
            return True

        elif cmd == "/list":
            sessions = self.list_sessions()
            if sessions:
                self.ui.print_info("Available sessions:")
                for s in sessions:
                    self.ui.console.print(f"  - {s}")
            else:
                self.ui.print_info("No saved sessions found.")
            return True

        elif cmd == "/clear":
            if self.manager:
                self.manager.clear_history()
            self._auto_save()
            self.ui.clear()
            self.ui.print_header()
            self.ui.print_success("Conversation cleared. Starting fresh.")
            return True

        elif cmd == "/verbose":
            self.mode = SessionMode.VERBOSE
            self.ui.verbose_worker = True
            self.ui.print_success("Verbose mode enabled. Worker output will be shown in detail.")
            return True

        elif cmd == "/quiet":
            self.mode = SessionMode.AUTO
            self.ui.verbose_worker = False
            self.ui.print_success("Quiet mode enabled. Worker output will be summarized.")
            return True

        elif cmd == "/history":
            if self.manager:
                self.ui.show_history(self.manager.get_history())
            else:
                self.ui.print_info("No history yet.")
            return True

        elif cmd == "/help":
            self._show_help()
            return True

        return False

    def _process_user_message(self, user_input: str):
        """Process a user message through the Manager Agent."""
        # Display user message
        self.ui.display_user_message(user_input)

        # Get response from Manager
        self.ui.display_manager_thinking("Analyzing your request...")

        try:
            response = self.manager.chat(user_input)

            # Display Worker results if any
            for result in response.worker_results:
                self.ui.display_worker_result(result)

            # Display Manager's response
            if response.content:
                self.ui.display_manager_message(response.content)

            # Auto-save after each turn
            self._auto_save()

        except ConnectionError:
            self.ui.print_error(
                "Could not connect to LLM API. "
                "Make sure the proxy is running at: "
                f"{self.settings.ORCHESTRATOR_API_BASE}"
            )
        except TimeoutError:
            self.ui.print_error("LLM API request timed out. Please try again.")
        except Exception as e:
            error_str = str(e).lower()
            if "connection" in error_str or "refused" in error_str:
                self.ui.print_error(
                    "Could not connect to LLM API. "
                    "Make sure the proxy is running at: "
                    f"{self.settings.ORCHESTRATOR_API_BASE}"
                )
            elif "auth" in error_str or "401" in error_str or "api_key" in error_str:
                self.ui.print_error(
                    "Authentication failed. Check your ORCHESTRATOR_API_KEY in .env"
                )
            elif "model" in error_str or "404" in error_str:
                self.ui.print_error(
                    f"Model '{self.settings.ORCHESTRATOR_MODEL}' not found or unavailable. "
                    "Check your ORCHESTRATOR_MODEL in .env"
                )
            else:
                logger.error(f"Manager error: {e}")
                self.ui.print_error(f"An unexpected error occurred: {e}")

    def start_interactive_mode(self):
        """Start the interactive session loop."""
        self._running = True
        self.ui.print_header()

        # Initialize Manager Agent
        self._init_manager()

        # Try to load latest session
        if self.load_session("latest_session"):
            self.ui.print_info("Previous session restored.")

        # Show settings
        settings_dict = {
            "Manager Model": self.settings.ORCHESTRATOR_MODEL,
            "Worker Model": self.settings.WORKER_MODEL,
            "Agent Path": str(self.settings.agent_path_resolved),
            "Mode": "Verbose" if self.ui.verbose_worker else "Quiet",
        }
        self.ui.print_settings(settings_dict)

        self.ui.print_info("Chat with the Manager Agent. Use /help for commands.")

        while self._running:
            try:
                # Get user input
                user_input = self.ui.get_user_input("You").strip()

                # Handle empty input
                if not user_input:
                    continue

                # Handle slash commands
                if user_input.startswith("/"):
                    if self._handle_slash_command(user_input):
                        continue
                    else:
                        self.ui.print_warning(f"Unknown command: {user_input}")
                        self.ui.print_info("Use /help for available commands.")
                        continue

                # Handle exit commands
                lower_input = user_input.lower()
                if lower_input in ("exit", "quit", "q"):
                    self.ui.print_info("Goodbye!")
                    break

                # Process through Manager Agent
                self._process_user_message(user_input)

            except KeyboardInterrupt:
                self.ui.print_warning("\nInterrupted. Type 'exit' to quit.")
                continue
            except EOFError:
                self.ui.print_info("\nGoodbye!")
                break

        # Final save before exit
        self._auto_save()
        self._running = False

    def _show_help(self):
        """Display help information."""
        help_text = """
## GOrchestrator - Intelligent AI Agent Manager

### How It Works
You chat with the **Manager Agent** (🧠), a Senior Software Architect AI.
The Manager understands your requests and decides when to delegate tasks
to the **Worker Agent** (👷), which executes code and terminal commands.

### Commands
| Command | Description |
|---------|-------------|
| `/save [name]` | Save session (default: manual_save) |
| `/load [name]` | Load session (default: latest_session) |
| `/list` | List available sessions |
| `/clear` | Clear conversation history |
| `/verbose` | Show detailed Worker output |
| `/quiet` | Show summarized Worker output |
| `/history` | Show conversation history |
| `/help` | Show this help |
| `exit` | Exit the application |

### Examples
- **"Hello!"** → Manager responds conversationally
- **"Create a Python script that..."** → Manager delegates to Worker
- **"What did the Worker do?"** → Manager explains the results
- **"Fix the error in..."** → Manager delegates fix to Worker

### Tips
- Be specific about what you want
- The Manager will ask clarifying questions if needed
- Review Worker results - the Manager will explain what was done
        """
        from rich.markdown import Markdown
        self.ui.console.print(Markdown(help_text))

"""
Session Engine - Interactive session manager for GOrchestrator.
Manages the conversation loop between User, Manager Agent, and Worker Agent.
"""

import atexit
import json
import logging
import os
import random
import re
import subprocess
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from ..ui.console import ConsoleUI
from ..utils.parser import parse_log_line
from .config import Settings, get_settings, reload_settings, write_env_value, _SUB_MANAGER_PROFILES_DIR
from .manager import ManagerAgent, ManagerResponse
from .sub_manager import SubManagerConfig, SubManagerRegistry, SubManagerResponse
from .llm_pool import LLMResponse
from .team import TeamConfig, TeamRegistry
from .checkpoint_manager import CheckpointManager
from .worker import AgentWorker, TaskResult, TaskStatus
from .worker_registry import WorkerConfig, WorkerRegistry

# New command system
from ..commands.parser import CommandParser
from ..commands.handlers import CommandHandler
from ..commands.completer import TabCompleter
from ..commands.help import HelpSystem

logger = logging.getLogger(__name__)


# Random session name components
_NAME_ADJECTIVES = [
    "Swift", "Bold", "Calm", "Dark", "Eager", "Fresh", "Grand", "Hazy",
    "Iron", "Jade", "Keen", "Lucid", "Mild", "Noble", "Open", "Prime",
    "Quick", "Rapid", "Sharp", "True", "Ultra", "Vivid", "Warm", "Zen",
]
_NAME_NOUNS = [
    "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot",
    "Galaxy", "Harbor", "Ignite", "Jupiter", "Krypton", "Lambda",
    "Mercury", "Nebula", "Orbit", "Phoenix", "Quantum", "Reactor",
    "Stellar", "Thunder", "Unity", "Vortex", "Warp", "Xenon",
]


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

    # Use absolute path based on project root (where main.py lives)
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    SESSIONS_DIR = _PROJECT_ROOT / ".gorchestrator" / "sessions"
    _LAST_SESSION_FILE = _PROJECT_ROOT / ".gorchestrator" / "last_session_id"

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
        self._confirm_mode = False
        self._atexit_registered = False

        # Session identity
        self.session_id: str | None = None
        self.session_name: str = ""
        self.session_created_at: str = ""

        # Ensure directories exist
        self.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

        # Worker registry
        self.worker_registry = WorkerRegistry(
            self._PROJECT_ROOT / ".gorchestrator" / "workers.json"
        )
        self.worker_registry.ensure_default(
            model=self.settings.WORKER_MODEL,
            profile=self.settings.WORKER_PROFILE,
        )

        # Sub-manager registry
        self.sub_manager_registry = SubManagerRegistry(
            self._PROJECT_ROOT / ".gorchestrator" / "sub_managers.json"
        )

        # Team registry
        self.team_registry = TeamRegistry(
            self._PROJECT_ROOT / ".gorchestrator" / "teams.json"
        )

        # Checkpoint manager (git-based undo system)
        self.checkpoint_manager = CheckpointManager(self.settings.agent_path_resolved)

        # Initialize new command system
        self.command_parser = CommandParser()
        self.command_handler = CommandHandler(self)
        self.tab_completer = TabCompleter()
        self.help_system = HelpSystem(self)

    @property
    def _session_dir(self) -> Path | None:
        """Directory for the current session's data."""
        if not self.session_id:
            return None
        return self.SESSIONS_DIR / self.session_id

    def _new_session(self, name: str = "") -> str:
        """Create a new session with a unique ID and optional or random name."""
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        self.session_created_at = datetime.now().isoformat()
        if name:
            self.session_name = name
        else:
            adj = random.choice(_NAME_ADJECTIVES)
            noun = random.choice(_NAME_NOUNS)
            self.session_name = f"{adj} {noun}"
        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._save_last_session_id()
        logger.info(f"New session created: {self.session_id}")
        return self.session_id

    def _save_last_session_id(self):
        """Persist the current session ID so we can resume on restart."""
        try:
            self._LAST_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._LAST_SESSION_FILE.write_text(self.session_id, encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save last session ID: {e}")

    def _get_last_session_id(self) -> str | None:
        """Read the last session ID from disk."""
        try:
            if self._LAST_SESSION_FILE.exists():
                sid = self._LAST_SESSION_FILE.read_text(encoding="utf-8").strip()
                if sid and (self.SESSIONS_DIR / sid).exists():
                    return sid
        except Exception:
            pass
        return None

    def get_tab_completions(self, cmd: str, arg: str) -> list[str]:
        """Provide tab completions for commands.

        Args:
            cmd: The base command (e.g., "/manager", "/worker", "/load")
            arg: The argument string after the command

        Returns:
            List of completion candidates
        """
        parts = arg.strip().split()
        
        # /manager profile → List available profiles
        if cmd == "/manager" and len(parts) == 1 and parts[0] == "profile":
            profiles_dir = Path(__file__).parent.parent / "core" / "manager_profiles"
            if profiles_dir.exists():
                return [f.stem for f in profiles_dir.glob("*.yaml")]
        
        # /config set → List available config keys
        elif cmd == "/config" and len(parts) >= 1 and parts[0] == "set" and len(parts) == 2:
            config_keys = [
                "ORCHESTRATOR_MODEL", "WORKER_MODEL",
                "ORCHESTRATOR_API_BASE", "WORKER_API_BASE",
                "ORCHESTRATOR_API_KEY", "WORKER_API_KEY",
                "WORKER_PROFILE", "MANAGER_PROFILE",
                "WORKER_TIMEOUT", "VERBOSE_WORKER"
            ]
            prefix = parts[1].upper()
            return [k for k in config_keys if k.startswith(prefix)]
        
        # /load → List available sessions
        elif cmd == "/load" and len(parts) <= 1:
            sessions = self.list_sessions()
            if len(parts) == 1:
                prefix = parts[0]
                return [s["session_id"] for s in sessions if s["session_id"].startswith(prefix)]
            else:
                return [s["session_id"] for s in sessions[:10]]  # Limit for performance
        
        return []

    def _validate_config_on_startup(self):
        """Run config validation at startup and display warnings/errors."""
        issues = self.settings.validate_config()
        if not issues:
            return

        for issue in issues:
            level = issue["level"]
            message = issue["message"]
            if level == "error":
                self.ui.print_error(f"Config: {message}")
            else:
                self.ui.print_warning(f"Config: {message}")

    def _init_manager(self):
        """Initialize the Manager Agent with UI callbacks."""
        def on_worker_output(line: str, worker_name: str = "worker"):
            entry = parse_log_line(line)
            self.ui.display_worker_step(entry, worker_name=worker_name)

        def on_thinking(text: str):
            self.ui.display_manager_thinking(text)

        def on_before_worker(task_description: str):
            self.checkpoint_manager.create(task_description[:50])

        def on_sub_manager_response(sm_response: SubManagerResponse):
            self.ui.display_sub_manager_response(sm_response)

        def on_llm_pool_response(llm_response: LLMResponse):
            self.ui.display_llm_pool_response(llm_response)

        self.manager = ManagerAgent(
            settings=self.settings,
            worker_registry=self.worker_registry,
            sub_manager_registry=self.sub_manager_registry,
            on_worker_output=on_worker_output,
            on_thinking=on_thinking,
            on_before_worker=on_before_worker,
            on_sub_manager_response=on_sub_manager_response,
            on_llm_pool_response=on_llm_pool_response,
        )

    # ================================================================
    # Session Management
    # ================================================================

    def save_session(self, name: str | None = None) -> Path:
        """Save the current session to its session directory."""
        if not self.session_id:
            self._new_session(name or "")

        session_dir = self._session_dir
        session_dir.mkdir(parents=True, exist_ok=True)
        filepath = session_dir / "session.json"

        # Build a short summary from last user message
        summary = ""
        if self.manager:
            for msg in reversed(self.manager.messages):
                if msg.role.value == "user":
                    summary = msg.content[:80]
                    break

        session_data = {
            "version": "3.0",
            "session_id": self.session_id,
            "session_name": name or self.session_name,
            "created_at": self.session_created_at,
            "saved_at": datetime.now().isoformat(),
            "mode": self.mode.value,
            "summary": summary,
            "message_count": len(self.manager.messages) if self.manager else 0,
            "manager_history": self.manager.export_history() if self.manager else [],
        }

        # Update session_name if user provided one
        if name:
            self.session_name = name

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            self._save_last_session_id()
            logger.info(f"Session saved to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            raise

    def load_session(self, identifier: str) -> bool:
        """Load a session by its ID or name."""
        filepath = self._find_session_file(identifier)
        if not filepath:
            logger.warning(f"Session not found: {identifier}")
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

            # Restore session identity
            self.session_id = session_data.get("session_id", filepath.parent.name)
            self.session_name = session_data.get("session_name", identifier)
            self.session_created_at = session_data.get("created_at", session_data.get("saved_at", ""))

            # Restore mode
            mode_str = session_data.get("mode", "auto")
            if mode_str == "verbose":
                self.mode = SessionMode.VERBOSE
                self.ui.verbose_worker = True
            else:
                self.mode = SessionMode.AUTO
                self.ui.verbose_worker = False

            self._save_last_session_id()
            logger.info(f"Session loaded: {self.session_id}")
            return True
        except json.JSONDecodeError as e:
            logger.error(f"Session file is corrupted: {e}")
            self.ui.print_error(f"Session '{identifier}' is corrupted: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return False

    def _find_session_file(self, identifier: str) -> Path | None:
        """Find a session file by ID or name. Returns the file path or None."""
        # Reject path traversal attempts
        if ".." in identifier or "/" in identifier or "\\" in identifier:
            logger.warning(f"Rejected path traversal attempt: {identifier}")
            return None

        # 1. Try exact ID match
        session_dir = self.SESSIONS_DIR / identifier
        if session_dir.is_dir() and (session_dir / "session.json").exists():
            return session_dir / "session.json"

        # 2. Legacy flat file
        legacy = self.SESSIONS_DIR / f"{identifier}.json"
        if legacy.is_file():
            return legacy

        # 3. Search by session name (case-insensitive)
        identifier_lower = identifier.lower()
        for d in self.SESSIONS_DIR.iterdir():
            if d.is_dir() and (d / "session.json").exists():
                try:
                    with open(d / "session.json", "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    if data.get("session_name", "").lower() == identifier_lower:
                        return d / "session.json"
                except Exception:
                    continue

        return None

    def list_sessions(self) -> list[dict]:
        """List all available sessions with metadata."""
        sessions = []
        # Scan session directories (new format: each session is a directory)
        for d in sorted(self.SESSIONS_DIR.iterdir(), key=os.path.getmtime, reverse=True):
            session_file = None
            if d.is_dir() and (d / "session.json").exists():
                session_file = d / "session.json"
                sid = d.name
            elif d.is_file() and d.suffix == ".json":
                # Legacy flat file
                session_file = d
                sid = d.stem
            else:
                continue

            info = {"session_id": sid}
            try:
                with open(session_file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                info["name"] = data.get("session_name", sid)
                info["saved_at"] = data.get("saved_at", "?")
                info["created_at"] = data.get("created_at", data.get("saved_at", "?"))
                info["summary"] = data.get("summary", "")[:50]
                info["messages"] = data.get("message_count", "?")
            except Exception:
                info["name"] = sid
                info["saved_at"] = "?"
                info["created_at"] = "?"
                info["summary"] = "(unreadable)"
                info["messages"] = "?"
            sessions.append(info)
        return sessions

    def _auto_save(self):
        """Automatically save the current session."""
        try:
            self.save_session()
        except Exception as e:
            logger.warning(f"Auto-save failed: {e}")

    def _cleanup_executors(self):
        """Shut down all thread pool executors on exit."""
        if hasattr(self, 'manager') and self.manager and hasattr(self.manager, 'shutdown'):
            self.manager.shutdown()
        if hasattr(self, 'manager') and self.manager:
            if hasattr(self.manager, '_sub_manager_agent') and self.manager._sub_manager_agent:
                if hasattr(self.manager._sub_manager_agent, 'shutdown'):
                    self.manager._sub_manager_agent.shutdown()

    # ================================================================
    # Slash Command Handler
    # ================================================================

    def _handle_slash_command(self, command: str) -> bool:
        """Handle a slash command."""
        # Önce yeni komut sistemiyle dene
        if command.strip().startswith(("/manager", "/worker", "/session", "/system", "/mode", "/help", "/submanager", "/team", "/sm")):
            cmd_obj = self.command_parser.parse(command)
            if cmd_obj and self.command_parser.validate(cmd_obj):
                # Yeni komut sistemini kullan
                return self.command_handler.handle(cmd_obj)
        
        # Eğer yeni sistemde yoksa eski sistemle dene (backward compatibility)
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        # Resolve aliases (consolidated in CommandParser)
        if cmd in CommandParser.ALIASES:
            resolved = CommandParser.ALIASES[cmd]
            # If alias had no arg, but user passed one, glue it
            parts2 = resolved.split(maxsplit=1)
            cmd = parts2[0]
            if len(parts2) > 1 and not arg:
                arg = parts2[1]

        # --- Help command ---
        if cmd == "/help":
            if arg:
                # Detaylı yardım
                return self.help_system.show_command_help(arg)
            else:
                # Ana yardım
                self.help_system.show_main_help()
                return True

        # --- Session commands ---
        if cmd == "/save":
            name = arg.strip() or None
            try:
                self.save_session(name)
                display_name = name or self.session_name
                self.ui.print_success(f"Session saved: {display_name} (ID: {self.session_id})")
            except Exception as e:
                self.ui.print_error(f"Failed to save: {e}")
            return True

        elif cmd == "/load":
            identifier = arg.strip()
            if not identifier:
                sessions = self.list_sessions()
                if not sessions:
                    self.ui.print_info("No saved sessions found.")
                    return True
                from rich.table import Table
                table = Table(title="Available Sessions", show_header=True, header_style="bold cyan")
                table.add_column("#", style="bold", width=3)
                table.add_column("ID", style="dim", max_width=22)
                table.add_column("Name", style="green")
                table.add_column("Created", style="cyan")
                table.add_column("Last Modified", style="dim")
                table.add_column("Messages", style="cyan", justify="right")
                table.add_column("Summary", style="dim", overflow="fold")
                for i, s in enumerate(sessions, 1):
                    created_at = s["created_at"]
                    last_modified = s["saved_at"]
                    
                    # Format dates
                    if created_at != "?":
                        try:
                            dt = datetime.fromisoformat(created_at)
                            created_at = dt.strftime("%Y-%m-%d %H:%M")
                        except Exception:
                            pass
                    
                    if last_modified != "?":
                        try:
                            dt = datetime.fromisoformat(last_modified)
                            last_modified = dt.strftime("%Y-%m-%d %H:%M")
                        except Exception:
                            pass
                    
                    table.add_row(str(i), s["session_id"], s.get("name", ""), 
                                 created_at, last_modified, str(s["messages"]), s["summary"])
                self.ui.console.print(table)
                self.ui.print_info("Usage: /load <session_id or name>")
                return True
            if self.load_session(identifier):
                msg_count = len(self.manager.messages) - 1
                self.ui.print_success(f"Session '{self.session_name}' loaded ({msg_count} messages)")
                if self.manager:
                    history = self.manager.get_history()
                    recent = history[-5:] if len(history) > 5 else history
                    if recent:
                        self.ui.print_info("--- Recent conversation ---")
                        self.ui.show_history(recent)
            else:
                self.ui.print_error(f"Session '{identifier}' not found.")
                sessions = self.list_sessions()
                if sessions:
                    names = [f"{s['session_id']} ({s.get('name', '')})" for s in sessions[:5]]
                    self.ui.print_info(f"Available: {', '.join(names)}")
            return True

        elif cmd == "/new":
            self._auto_save()
            self._new_session(arg.strip() or "")
            if self.manager:
                self.manager.clear_history()
            else:
                self._init_manager()
            self.ui.print_success(f"New session started: {self.session_name} (ID: {self.session_id})")
            return True

        elif cmd == "/list":
            sessions = self.list_sessions()
            if sessions:
                from rich.table import Table
                table = Table(title="Saved Sessions", show_header=True, header_style="bold cyan")
                table.add_column("ID", style="dim", max_width=22)
                table.add_column("Name", style="green")
                table.add_column("Saved At", style="dim")
                table.add_column("Messages", style="cyan", justify="right")
                table.add_column("Summary", style="dim", overflow="fold")
                active_id = self.session_id or ""
                for s in sessions:
                    saved_at = s["saved_at"]
                    if saved_at != "?":
                        try:
                            dt = datetime.fromisoformat(saved_at)
                            saved_at = dt.strftime("%Y-%m-%d %H:%M")
                        except Exception:
                            pass
                    marker = " *" if s["session_id"] == active_id else ""
                    table.add_row(s["session_id"], s.get("name", "") + marker, saved_at, str(s["messages"]), s["summary"])
                self.ui.console.print(table)
                if active_id:
                    self.ui.print_info(f"Active session: {active_id} (*)")
            else:
                self.ui.print_info("No saved sessions found.")
            return True

        elif cmd == "/clear":
            self._auto_save()
            self._new_session()
            if self.manager:
                self.manager.clear_history()
            else:
                self._init_manager()
            self.ui.clear()
            self.ui.print_header()
            self.ui.print_success(f"Conversation cleared. New session: {self.session_name} (ID: {self.session_id})")
            return True

        elif cmd == "/clearterminal":
            self.ui.clear()
            self.ui.print_header()
            return True

        # --- Display mode commands ---
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
                self.ui.show_full_history(self.manager.get_full_history())
            else:
                self.ui.print_info("No history yet.")
            return True

        # --- Model command ---
        elif cmd == "/model":
            model_name = arg.strip()
            if not model_name:
                self.ui.print_info(f"Current Manager model: {self.settings.ORCHESTRATOR_MODEL}")
                self.ui.print_info(f"Current Worker model: {self.settings.WORKER_MODEL}")
                self.ui.print_info("Usage: /model <manager|worker> <model_name>")
                return True
            parts_model = model_name.split(maxsplit=1)
            if len(parts_model) == 2 and parts_model[0] in ("manager", "worker"):
                target, new_model = parts_model
                if target == "manager":
                    self.settings.ORCHESTRATOR_MODEL = new_model
                    write_env_value("ORCHESTRATOR_MODEL", new_model)
                    self.ui.print_success(f"Manager model changed to: {new_model} (saved to .env)")
                else:
                    self.settings.WORKER_MODEL = new_model
                    write_env_value("WORKER_MODEL", new_model)
                    # Sync primary worker in registry
                    primary = self.worker_registry.get_primary()
                    if primary:
                        self.worker_registry.update_model(primary.name, new_model)
                    self._refresh_manager_tools()
                    self.ui.print_success(f"Worker model changed to: {new_model} (saved to .env)")
            else:
                # Default: change manager model
                self.settings.ORCHESTRATOR_MODEL = model_name
                write_env_value("ORCHESTRATOR_MODEL", model_name)
                self.ui.print_success(f"Manager model changed to: {model_name} (saved to .env)")
            active_workers = self.worker_registry.get_active_workers()
            active_names = ", ".join(wc.name for wc in active_workers) or "(none)"
            settings_dict = {
                "Manager Model": self.settings.ORCHESTRATOR_MODEL,
                "Worker Model": self.settings.WORKER_MODEL,
                "Active Workers": active_names,
                "Agent Path": str(self.settings.agent_path_resolved),
                "Mode": "Verbose" if self.ui.verbose_worker else "Quiet",
            }
            self.ui.print_settings(settings_dict)
            return True

        # --- Config commands (DEPRECATED) ---
        elif cmd == "/config":
            self.ui.print_warning("⚠️  /config command deprecated")
            self.ui.print_info("")
            self.ui.print_info("Use /manager or /worker commands instead:")
            self.ui.print_info("  /manager model <name> [--global]")
            self.ui.print_info("  /manager api <base> [key] [--global]")
            self.ui.print_info("  /worker model <name> <model>")
            self.ui.print_info("  /worker api <name> <base> [key]")
            return True

        # --- Worker management ---
        elif cmd == "/worker":
            self._handle_worker_command(arg.strip())
            return True

        # --- Sub-manager management ---
        elif cmd == "/submanager":
            self._handle_submanager_command(arg.strip())
            return True

        # --- Team management ---
        elif cmd == "/team":
            self._handle_team_command(arg.strip())
            return True

        # --- Manager management ---
        elif cmd == "/manager":
            return self._handle_manager_command(arg.strip())

        # --- Confirm mode ---
        elif cmd == "/confirm":
            sub = arg.strip().lower()
            if sub == "on":
                self._confirm_mode = True
                self.ui.print_success("Confirm mode ON. You will be asked before Worker executes tasks.")
            elif sub == "off":
                self._confirm_mode = False
                self.ui.print_success("Confirm mode OFF. Worker tasks will run automatically.")
            else:
                status = "ON" if self._confirm_mode else "OFF"
                self.ui.print_info(f"Confirm mode is {status}. Usage: /confirm <on|off>")
            return True

        # --- Undo/Checkpoint ---
        elif cmd == "/undo":
            success, msg = self.checkpoint_manager.restore()
            if success:
                remaining = len(self.checkpoint_manager.stack)
                self.ui.print_success(f"Reverted to last checkpoint. Worker changes undone. ({remaining} checkpoints remaining)")
            else:
                self.ui.print_warning(msg)
            return True

        elif cmd == "/checkpoints":
            checkpoints = self.checkpoint_manager.list_checkpoints()
            if checkpoints:
                from rich.table import Table
                table = Table(title="Git Checkpoints", show_header=True, header_style="bold cyan")
                table.add_column("#", style="bold", width=3)
                table.add_column("Tag", style="green")
                table.add_column("Date", style="dim")
                for i, tag in enumerate(checkpoints, 1):
                    # Extract date from tag name: gorchestrator-checkpoint-YYYYMMDD_HHMMSS
                    date_part = tag.replace("gorchestrator-checkpoint-", "")
                    try:
                        dt = datetime.strptime(date_part, "%Y%m%d_%H%M%S")
                        date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        date_str = date_part
                    table.add_row(str(i), tag, date_str)
                self.ui.console.print(table)
            else:
                self.ui.print_info("No checkpoints found. Checkpoints are created before Worker executions.")
            return True

        return False

    def _process_user_message(self, user_input: str):
        """Process a user message through the Manager Agent."""
        # Display user message
        self.ui.display_user_message(user_input)

        # Get response from Manager
        self.ui.display_manager_thinking("Analyzing your request...")

        try:
            # If confirm mode is on, we intercept before Worker runs
            if self._confirm_mode:
                response = self._process_with_confirmation(user_input)
            else:
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
                    f"Cannot connect to {self.settings.ORCHESTRATOR_API_BASE}. "
                    "Is the proxy running? Use /config show to check."
                )
            elif "auth" in error_str or "401" in error_str or "api_key" in error_str:
                self.ui.print_error(
                    f"API key rejected by {self.settings.ORCHESTRATOR_API_BASE}. "
                    "Check ORCHESTRATOR_API_KEY in .env"
                )
            elif "model" in error_str or "404" in error_str:
                self.ui.print_error(
                    f"Model '{self.settings.ORCHESTRATOR_MODEL}' not found at "
                    f"{self.settings.ORCHESTRATOR_API_BASE}. "
                    "Use /model to change or /config show to check."
                )
            else:
                logger.error(f"Manager error: {e}")
                self.ui.print_error(f"Unexpected error: {e}")

    def _process_with_confirmation(self, user_input: str) -> ManagerResponse:
        """Process with user confirmation before Worker tasks execute."""
        original_confirm = getattr(self.manager, '_confirm_before_worker', None)
        self.manager._confirm_before_worker = self._ask_worker_confirmation

        try:
            response = self.manager.chat(user_input)
        finally:
            self.manager._confirm_before_worker = original_confirm

        return response

    def _ask_worker_confirmation(self, task_description: str) -> bool:
        """Ask user to confirm before Worker executes a task."""
        self.ui.console.print()
        self.ui.console.print(f"[bold yellow]Worker wants to execute:[/bold yellow]")
        self.ui.console.print(f"  {task_description[:200]}")
        return self.ui.confirm("Proceed with this task?", default=True)

    def start_interactive_mode(self):
        """Start the interactive session loop."""
        self._running = True
        self.ui.print_header()

        # Register crash-safe auto-save
        if not self._atexit_registered:
            atexit.register(self._auto_save)
            atexit.register(self._cleanup_executors)
            self._atexit_registered = True

        # Validate config on startup
        self._validate_config_on_startup()

        # Initialize Manager Agent
        self._init_manager()

        # Try to resume last session or create new one
        last_sid = self._get_last_session_id()
        session_status = "new"
        msg_count = 0
        if last_sid and self.load_session(last_sid):
            msg_count = len(self.manager.messages) - 1
            session_status = "restored"
        else:
            self._new_session()

        # Show dashboard
        primary = self.worker_registry.get_primary()
        workers_info = []
        for wc in self.worker_registry.list_all():
            workers_info.append({
                "name": wc.name,
                "model": wc.model,
                "profile": wc.profile,
                "active": wc.active,
                "primary": primary and wc.name == primary.name,
                "api_base": wc.api_base,
            })
        sub_managers_info = []
        for sm in self.sub_manager_registry.list_all():
            sub_managers_info.append({
                "name": sm.name,
                "profile": sm.profile,
                "model": sm.model,
                "active": sm.active,
                "description": sm.description,
            })
        active_team = self.team_registry.get_active()
        active_team_info = None
        if active_team:
            active_team_info = {
                "name": active_team.name,
                "main_manager_profile": active_team.main_manager_profile,
                "sub_manager_names": active_team.sub_manager_names,
            }
        self.ui.print_dashboard({
            "session_name": self.session_name,
            "session_status": session_status,
            "msg_count": msg_count,
            "manager_model": self.settings.ORCHESTRATOR_MODEL,
            "api_base": self.settings.ORCHESTRATOR_API_BASE,
            "workers": workers_info,
            "sub_managers": sub_managers_info,
            "active_team": active_team_info,
            "parallel_llms": [
                {"name": c.name, "model": c.model}
                for c in self.manager.llm_pool.list_all()
            ] if self.manager else [],
            "mode": "Verbose" if self.ui.verbose_worker else "Quiet",
            "confirm": "ON" if self._confirm_mode else "OFF",
        })

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
                self._auto_save()
                continue
            except EOFError:
                self.ui.print_info("\nGoodbye!")
                break

        # Final save before exit
        self._auto_save()
        self._running = False

    def _show_worker_list(self):
        """Display the worker list table."""
        workers = self.worker_registry.list_all()
        if not workers:
            self.ui.print_info("No workers configured.")
            return True
        from rich.table import Table
        primary = self.worker_registry.get_primary()
        table = Table(title="Workers", show_header=True, header_style="bold cyan")
        table.add_column("Name", style="green")
        table.add_column("Model", style="dim")
        table.add_column("Profile", style="dim")
        table.add_column("API", style="dim", max_width=30)
        table.add_column("Status", style="bold")
        for wc in workers:
            if wc.active and primary and wc.name == primary.name:
                status = "[green]active * (primary)[/green]"
            elif wc.active:
                status = "[green]active *[/green]"
            else:
                status = "[dim]inactive[/dim]"
            api_display = wc.api_base or "[dim]default[/dim]"
            table.add_row(wc.name, wc.model, wc.profile, api_display, status)
        self.ui.console.print(table)
        return True

    def _handle_worker_command(self, arg: str):
        """Handle /worker sub-commands."""
        parts = arg.split()
        sub = parts[0].lower() if parts else ""

        if sub == "list" or not sub:
            self._show_worker_list()
            return True

        elif sub == "add":
            # /worker add <name> [model] [profile]
            if len(parts) < 2:
                self.ui.print_info("Usage: /worker add <name> [model] [profile]")
                return True
            name = parts[1]
            model = parts[2] if len(parts) > 2 else self.settings.WORKER_MODEL
            profile = parts[3] if len(parts) > 3 else self.settings.WORKER_PROFILE
            try:
                wc = self.worker_registry.add(name, model, profile)
                self.ui.print_success(f"Worker '{wc.name}' added")
                self._refresh_manager_tools()
                self._show_worker_list()
                return True
            except ValueError as e:
                self.ui.print_error(str(e))
                return True

        elif sub == "remove":
            if len(parts) < 2:
                self.ui.print_info("Usage: /worker remove <name>")
                return True
            name = parts[1]
            if self.worker_registry.remove(name):
                self.ui.print_success(f"Worker '{name}' removed")
                self._apply_active_worker()
                self._refresh_manager_tools()
                self._show_worker_list()
                return True
            else:
                self.ui.print_error(f"Worker '{name}' not found")
                return True

        elif sub == "set":
            # /worker set <name> active|inactive|primary
            if len(parts) < 3:
                self.ui.print_info("Usage: /worker set <name> active|inactive|primary")
                return True
            name = parts[1]
            state = parts[2].lower()
            if state == "active":
                if self.worker_registry.set_active(name):
                    self._apply_active_worker()
                    self._refresh_manager_tools()
                    self.ui.print_success(f"Worker '{name}' is now active")
                    self._show_worker_list()
                    return True
                else:
                    self.ui.print_error(f"Worker '{name}' not found")
                    return True
            elif state in ("inactive", "deactive"):
                if self.worker_registry.set_inactive(name):
                    self._apply_active_worker()
                    self._refresh_manager_tools()
                    self.ui.print_success(f"Worker '{name}' is now inactive")
                    self._show_worker_list()
                    return True
                else:
                    self.ui.print_error(f"Worker '{name}' not found")
                    return True
            elif state == "primary":
                # Move worker to front of registry (primary = first active)
                if self.worker_registry.set_primary(name):
                    self._apply_active_worker()
                    self._refresh_manager_tools()
                    self.ui.print_success(f"Worker '{name}' is now primary")
                    self._show_worker_list()
                    return True
                else:
                    self.ui.print_error(f"Worker '{name}' not found or not active")
                    return True
            else:
                self.ui.print_info("Usage: /worker set <name> active|inactive|primary")
                return True

        elif sub == "show":
            if len(parts) < 2:
                self.ui.print_info("Usage: /worker show <name>")
                return True
            name = parts[1]
            wc = self.worker_registry.get(name)
            if wc:
                settings_dict = {
                    "Name": wc.name,
                    "Model": wc.model,
                    "Profile": wc.profile,
                    "Status": "Active" if wc.active else "Inactive",
                    "Tool": f"delegate_to_{wc.name}",
                    "API Base": wc.api_base or "(default)",
                    "API Key": f"****...{wc.api_key[-4:]}" if wc.api_key and len(wc.api_key) > 4 else "(default)",
                }
                self.ui.print_settings(settings_dict)
                return True
            else:
                self.ui.print_error(f"Worker '{name}' not found")
                return True

        elif sub == "model":
            # /worker model <name> <model>
            if len(parts) < 3:
                self.ui.print_info("Usage: /worker model <name> <model>")
                return True
            name = parts[1]
            new_model = parts[2]
            if self.worker_registry.update_model(name, new_model):
                self.ui.print_success(f"Worker '{name}' model changed to: {new_model}")
                wc = self.worker_registry.get(name)
                if wc and wc.active:
                    self._apply_active_worker()
                self._refresh_manager_tools()
                self._show_worker_list()
                return True
            else:
                self.ui.print_error(f"Worker '{name}' not found")
                return True

        elif sub == "profile":
            # /worker profile <name> <profile>
            if len(parts) < 3:
                self.ui.print_info("Usage: /worker profile <name> <profile>")
                return True
            name = parts[1]
            new_profile = parts[2]
            if self.worker_registry.update_profile(name, new_profile):
                self.ui.print_success(f"Worker '{name}' profile changed to: {new_profile}")
                wc = self.worker_registry.get(name)
                if wc and wc.active:
                    self._apply_active_worker()
                self._refresh_manager_tools()
                self._show_worker_list()
                return True
            else:
                self.ui.print_error(f"Worker '{name}' not found")
                return True

        elif sub == "api":
            # /worker api <name> <api_base> [api_key]
            if len(parts) < 3:
                self.ui.print_info("Usage: /worker api <name> <api_base> [api_key]")
                self.ui.print_info("Example: /worker api coder https://api.z.ai sk-key123")
                return True
            name = parts[1]
            api_base = parts[2]
            api_key = parts[3] if len(parts) > 3 else None
            if self.worker_registry.update_api(name, api_base, api_key):
                self.ui.print_success(f"Worker '{name}' API set to: {api_base}")
                self._refresh_manager_tools()
                self._show_worker_list()
                return True
            else:
                self.ui.print_error(f"Worker '{name}' not found")
                return True

        else:
            self.ui.print_info("Usage: /worker <list|add|remove|set|show|model|profile|api>")
            return True

    def _apply_active_worker(self):
        """Sync primary worker's settings to .env and propagate to manager/worker."""
        primary = self.worker_registry.get_primary()
        if primary:
            self.settings.WORKER_MODEL = primary.model
            self.settings.WORKER_PROFILE = primary.profile
            write_env_value("WORKER_MODEL", primary.model)
            write_env_value("WORKER_PROFILE", primary.profile)
        if self.manager:
            self.manager.settings = self.settings
            self.manager.worker.settings = self.settings

    def _refresh_manager_tools(self):
        """Refresh Manager's system prompt and tools after worker registry changes."""
        if self.manager:
            self.manager.refresh_system_prompt()

    def _show_help(self):
        """Display help information."""
        help_text = """
## GOrchestrator - Intelligent AI Agent Manager

### How It Works
You chat with the **Manager Agent**, a Senior Software Architect AI.
The Manager understands your requests and decides when to delegate tasks
to the **Worker Agent**, which executes code and terminal commands.

### Session Commands
| Command | Alias | Description |
|---------|-------|-------------|
| `/save [name]` | `/s` | Save current session |
| `/load [id or name]` | | Load session by ID or name (shows list if no arg) |
| `/list` | `/l` | List all saved sessions |
| `/new [name]` | | Start a new session (random name if omitted) |
| `/clear` | | Clear conversation and start new session |
| `/clearterminal` | `/ct` | Clear terminal screen only |
| `/history` | | Show full conversation history |

### Display Commands
| Command | Description |
|---------|-------------|
| `/verbose` | Show detailed Worker output |
| `/quiet` | Show summarized Worker output |

### Config Commands
| Command | Description |
|---------|-------------|
| `/model [manager\\|worker] <name>` | Change model (saved to .env) |
| `/config show` | Show current configuration |
| `/config reload` | Reload .env file |
| `/config validate` | Check config for issues |
| `/config set <KEY> <VALUE>` | Set a config value (saved to .env) |

### Worker Management
| Command | Alias | Description |
|---------|-------|-------------|
| `/worker list` | `/w list` | List all worker profiles |
| `/worker add <name> [model] [profile]` | | Add a new worker |
| `/worker remove <name>` | | Remove a worker |
| `/worker set <name> active` | | Activate a worker (multiple can be active) |
| `/worker set <name> inactive` | | Deactivate a worker |
| `/worker set <name> primary` | | Set as primary worker (.env sync) |
| `/worker show <name>` | | Show worker details (model, profile, API, tool) |
| `/worker model <name> <model>` | | Change a worker's model |
| `/worker profile <name> <profile>` | | Change a worker's profile |
| `/worker api <name> <url> [key]` | | Set per-worker API endpoint |

### Config Aliases
- `/config set manager <model>` → sets ORCHESTRATOR_MODEL
- `/config set worker <model>` → sets WORKER_MODEL

### Multi-Worker
- Multiple workers can be **active** simultaneously
- The **primary** worker's settings are written to `.env`
- Manager can delegate to multiple workers in parallel
- Manager chooses which worker(s) to use based on the task
- Each worker can have its own API endpoint (`/worker api`)

### Safety Commands
| Command | Description |
|---------|-------------|
| `/confirm on\\|off` | Ask before Worker executes |
| `/undo` | Revert last Worker changes (git) |
| `/checkpoints` | List available git checkpoints |

### Other
| Command | Alias | Description |
|---------|-------|-------------|
| `/help` | `/h` | Show this help |
| `exit` | `q` | Exit the application |

### Input Tips
- **Tab**: Autocomplete slash commands and sub-commands
- **Arrow Up/Down**: Browse input history
- **Ctrl+J**: Insert new line
- **Multi-line paste**: Paste multi-line text directly
        """
        from rich.markdown import Markdown
        self.ui.console.print(Markdown(help_text))

    # ================================================================
    # Manager Command Handlers
    # ================================================================

    def _handle_manager_command(self, arg: str) -> bool:
        """Handle /manager commands (worker gibi zengin)."""
        parts = arg.strip().split()
        if not parts or parts[0] == "show":
            return self._manager_show_config()
        
        sub = parts[0].lower()
        
        # Check for --global flag
        persistent = "--global" in parts
        if persistent:
            parts = [p for p in parts if p != "--global"]
        
        # MEVCUT KOMUTLAR (korunacak)
        if sub == "list":
            return self._manager_list_profiles()
        elif sub == "profile":
            if len(parts) >= 2:
                return self._manager_set_profile(parts[1])
            else:
                # /manager profile (arg yok) → profilleri listele
                return self._manager_list_profiles()
        
        # YENİ KOMUTLAR (Worker gibi zengin)
        elif sub == "model" and len(parts) >= 2:
            return self._manager_set_model(parts[1], persistent=persistent)
        elif sub == "api" and len(parts) >= 2:
            api_base = parts[1]
            api_key = parts[2] if len(parts) > 2 else None
            return self._manager_set_api(api_base, api_key, persistent=persistent)
        elif sub == "prompt" and len(parts) >= 2:
            prompt_text = " ".join(parts[1:])
            return self._manager_set_prompt(prompt_text)
        elif sub == "rules":
            if len(parts) >= 2 and parts[1] == "show":
                return self._manager_show_rules()
            elif len(parts) >= 2 and parts[1] == "edit":
                return self._manager_edit_rules()
            else:
                self.ui.print_info("Usage: /manager rules <show|edit>")
                return False
        elif sub == "temp" and len(parts) >= 2:
            try:
                temp = float(parts[1])
                return self._manager_set_temperature(temp)
            except ValueError:
                self.ui.print_error("Temperature must be a number (0.0-2.0)")
                return False
        elif sub == "tokens" and len(parts) >= 2:
            try:
                tokens = int(parts[1])
                return self._manager_set_max_tokens(tokens)
            except ValueError:
                self.ui.print_error("Max tokens must be an integer")
                return False
        elif sub == "llm":
            return self._handle_manager_llm_command(" ".join(parts[1:]) if len(parts) > 1 else "")
        else:
            self.ui.print_error("Usage: /manager show|list|profile [name]|model <name> [--global]|api <base> [key] [--global]|prompt <text>|rules show|edit|temp <val>|tokens <val>|llm <sub>")
            self.ui.print_info("")
            self.ui.print_info("Examples:")
            self.ui.print_info("  /manager show                    → Show current settings")
            self.ui.print_info("  /manager profile                  → List profiles")
            self.ui.print_info("  /manager profile default          → Set profile to 'default'")
            self.ui.print_info("  /manager model glm-4.7           → Set model (session)")
            self.ui.print_info("  /manager model glm-4.7 --global → Save model to .env")
            self.ui.print_info("  /manager api https://api.z.ai   → Set API base (session)")
            self.ui.print_info("  /manager api https://api.z.ai --global → Save API to .env")
            self.ui.print_info("  /manager llm list                → List parallel LLMs")
            self.ui.print_info("  /manager llm add <name> <model>  → Add parallel LLM")
            return False
    def _manager_show_config(self) -> bool:
        """Display current manager configuration."""
        config = self.settings.get_manager_config()
        from rich.table import Table
        
        table = Table(title="Current Manager Configuration", show_header=True, header_style="bold cyan")
        table.add_column("Setting", style="green")
        table.add_column("Value", style="cyan")
        
        # get_manager_config() already applies overrides, just display values
        table.add_row("Profile", self.settings.MANAGER_PROFILE)
        table.add_row("Model", config.get("model", "N/A"))
        table.add_row("API Base", config.get("api_base", "N/A"))
        api_key = config.get('api_key', '')
        table.add_row("API Key", f"****...{api_key[-4:]}" if api_key and len(api_key) > 4 else "****")
        table.add_row("Temperature", str(config.get("temperature", "default")))
        table.add_row("Max Tokens", str(config.get("max_tokens", "default")))
        thinking_cfg = config.get("thinking")
        if thinking_cfg and thinking_cfg.get("enabled"):
            table.add_row("Thinking", f"enabled (budget: {thinking_cfg.get('budget_tokens', 'N/A')})")
        else:
            table.add_row("Thinking", "disabled")
        table.add_row("Custom Prompt", "Yes" if config.get("system_prompt") else "No (default)")
        
        self.ui.console.print(table)
        return True

    def _manager_list_profiles(self) -> bool:
        """List all available manager profiles."""
        from rich.table import Table
        
        profiles_dir = Path(__file__).parent.parent / "core" / "manager_profiles"
        if not profiles_dir.exists():
            self.ui.print_error(f"Manager profiles directory not found: {profiles_dir}")
            return False
        
        profile_files = list(profiles_dir.glob("*.yaml"))
        if not profile_files:
            self.ui.print_info("No manager profiles found.")
            return True

        import yaml

        table = Table(title="Available Manager Profiles", show_header=True, header_style="bold cyan")
        table.add_column("Profile", style="green")
        table.add_column("Description", style="cyan")
        table.add_column("Status", style="yellow")

        for profile_file in profile_files:
            profile_name = profile_file.stem
            is_active = profile_name == self.settings.MANAGER_PROFILE
            status = "✓ Active" if is_active else ""

            # Try to read description from YAML
            description = ""
            try:
                with open(profile_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    description = data.get("description", "")
            except Exception:
                pass
            
            table.add_row(profile_name, description, status)
        
        self.ui.console.print(table)
        return True

    def _manager_set_profile(self, profile_name: str) -> bool:
        """Change manager profile and reload settings."""
        # Validate profile exists
        profiles_dir = Path(__file__).parent.parent / "core" / "manager_profiles"
        profile_path = profiles_dir / f"{profile_name}.yaml"
        
        if not profile_path.exists():
            self.ui.print_error(f"Manager profile '{profile_name}' not found.")
            self._manager_list_profiles()
            return False
        
        # Update .env
        try:
            write_env_value("MANAGER_PROFILE", profile_name)
            self.ui.print_success(f"Manager profile changed to: {profile_name}")
        except Exception as e:
            self.ui.print_error(f"Failed to update .env: {e}")
            return False
        
        # Reload settings
        try:
            reload_settings()
            self.settings = get_settings()
            self.ui.print_info("Settings reloaded.")
        except Exception as e:
            self.ui.print_error(f"Failed to reload settings: {e}")
            return False
        
        # Reinitialize manager with new config, preserving conversation history
        try:
            saved_history = self.manager.export_history() if self.manager else None
            self._init_manager()
            if saved_history and self.manager:
                self.manager.import_history(saved_history)
            self.ui.print_success("Manager reinitialized with new profile.")
        except Exception as e:
            self.ui.print_error(f"Failed to reinitialize manager: {e}")
            return False
        
        return True
    def _manager_set_model(self, model: str, persistent: bool = False) -> bool:
        """Change manager model at runtime.

        Args:
            model: The model name to use
            persistent: If True, write to .env; if False, session-based only

        Returns:
            True if successful
        """
        try:
            if persistent:
                # Global: write to .env and reload
                write_env_value("ORCHESTRATOR_MODEL", model)
                self.settings = reload_settings()
                self.ui.print_success(f"Manager model saved to .env: {model}")
            else:
                # Session-based: use Settings override
                self.settings.MANAGER_MODEL_OVERRIDE = model
                self.ui.print_success(f"Manager model changed to: {model} (session-based)")

            # Re-init manager, preserving conversation history
            saved_history = self.manager.export_history() if self.manager else None
            self._init_manager()
            if saved_history and self.manager:
                self.manager.import_history(saved_history)
            return True
        except Exception as e:
            self.ui.print_error(f"Failed to change model: {e}")
            return False

    def _manager_set_api(self, api_base: str, api_key: str | None, persistent: bool = False) -> bool:
        """Change manager API settings at runtime.

        Args:
            api_base: The API base URL
            api_key: Optional API key
            persistent: If True, write to .env; if False, session-based only

        Returns:
            True if successful
        """
        try:
            if persistent:
                # Global: write to .env and reload
                write_env_value("ORCHESTRATOR_API_BASE", api_base)
                if api_key:
                    write_env_value("ORCHESTRATOR_API_KEY", api_key)
                self.settings = reload_settings()
                self.ui.print_success(f"Manager API saved to .env: base={api_base}")
            else:
                # Session-based: use Settings override
                self.settings.MANAGER_API_BASE_OVERRIDE = api_base
                if api_key:
                    self.settings.MANAGER_API_KEY_OVERRIDE = api_key
                self.ui.print_success(f"Manager API changed: base={api_base} (session-based)")

            # Re-init manager, preserving conversation history
            saved_history = self.manager.export_history() if self.manager else None
            self._init_manager()
            if saved_history and self.manager:
                self.manager.import_history(saved_history)
            return True
        except Exception as e:
            self.ui.print_error(f"Failed to change API: {e}")
            return False

    def _manager_set_prompt(self, prompt_text: str) -> bool:
        """Override system prompt for this session (non-persistent)."""
        if not self.manager:
            self.ui.print_error("Manager not initialized")
            return False
        
        try:
            self.manager.messages[0].content = prompt_text
            self.ui.print_success("System prompt updated for this session (not saved)")
            return True
        except Exception as e:
            self.ui.print_error(f"Failed to update prompt: {e}")
            return False

    def _manager_show_rules(self) -> bool:
        """Display current manager rules."""
        config = self.settings.get_manager_config()
        rules = config.get("rules", {})
        
        from rich.table import Table
        table = Table(title="Manager Rules", show_header=True, header_style="bold cyan")
        table.add_column("Rule", style="green")
        table.add_column("Value", style="cyan")
        
        for key, value in rules.items():
            table.add_row(key, str(value))
        
        if not rules:
            self.ui.print_info("No rules configured (see manager_profiles/rules.yaml)")
        else:
            self.ui.console.print(table)
        return True

    def _manager_edit_rules(self) -> bool:
        """Open rules.yaml in default editor."""
        rules_path = Path(__file__).parent.parent / "core" / "manager_profiles" / "rules.yaml"
        
        if not rules_path.exists():
            self.ui.print_info("Creating rules.yaml from template...")
            import shutil
            shutil.copy(Path(__file__).parent.parent / "core" / "manager_profiles" / "custom.yaml", rules_path)
            self.ui.print_success(f"Created rules.yaml from custom.yaml template")
        
        editor = os.environ.get("EDITOR", "notepad" if os.name == "nt" else "nano")
        
        try:
            subprocess.run([editor, str(rules_path)], check=True)
            self.ui.print_success(f"Opened {rules_path} in {editor}")
            return True
        except Exception as e:
            self.ui.print_error(f"Failed to open editor: {e}")
            return False

    def _manager_set_temperature(self, temp: float) -> bool:
        """Change manager temperature at runtime via override (session-only, not persisted)."""
        try:
            temp_val = float(temp)
            self.settings.MANAGER_TEMP_OVERRIDE = str(temp_val)
            # Re-init manager, preserving conversation history
            saved_history = self.manager.export_history() if self.manager else None
            self._init_manager()
            if saved_history and self.manager:
                self.manager.import_history(saved_history)
            self.ui.print_success(f"Manager temperature set to {temp_val} (session override)")
            return True
        except (ValueError, TypeError):
            self.ui.print_error(f"Invalid temperature value: {temp}")
            return False

    def _manager_set_max_tokens(self, tokens: int) -> bool:
        """Change manager max tokens at runtime via override (session-only, not persisted)."""
        try:
            tokens_val = int(tokens)
            if tokens_val < 1:
                self.ui.print_error("max_tokens must be >= 1")
                return False
            self.settings.MANAGER_TOKENS_OVERRIDE = str(tokens_val)
            # Re-init manager, preserving conversation history
            saved_history = self.manager.export_history() if self.manager else None
            self._init_manager()
            if saved_history and self.manager:
                self.manager.import_history(saved_history)
            self.ui.print_success(f"Manager max_tokens set to {tokens_val} (session override)")
            return True
        except (ValueError, TypeError):
            self.ui.print_error(f"Invalid max_tokens value: {tokens}")
            return False

    # ================================================================
    # Sub-Manager Command Handlers
    # ================================================================

    def _show_submanager_list(self):
        """Display the sub-manager list table."""
        sub_managers = self.sub_manager_registry.list_all()
        if not sub_managers:
            self.ui.print_info("No sub-managers configured. Use /submanager add <name> <profile> [model]")
            return True
        from rich.table import Table
        table = Table(title="Sub-Managers (Advisors)", show_header=True, header_style="bold cyan")
        table.add_column("Name", style="green")
        table.add_column("Profile", style="dim")
        table.add_column("Model", style="dim")
        table.add_column("Description", style="dim", max_width=40)
        table.add_column("API", style="dim", max_width=25)
        table.add_column("Status", style="bold")
        for sm in sub_managers:
            status = "[green]active *[/green]" if sm.active else "[dim]inactive[/dim]"
            api_display = sm.api_base or "[dim]from profile[/dim]"
            table.add_row(sm.name, sm.profile, sm.model, sm.description or "", api_display, status)
        self.ui.console.print(table)
        return True

    def _handle_submanager_command(self, arg: str):
        """Handle /submanager sub-commands."""
        parts = arg.split()
        sub = parts[0].lower() if parts else ""

        if sub == "list" or not sub:
            self._show_submanager_list()
            return True

        elif sub == "add":
            # /submanager add <name> <profile> [model]
            if len(parts) < 3:
                self.ui.print_info("Usage: /submanager add <name> <profile> [model]")
                self.ui.print_info("Example: /submanager add architect architect claude-3-5-sonnet-20241022")
                self.ui.print_info("")
                # List available profiles
                if _SUB_MANAGER_PROFILES_DIR.exists():
                    profiles = [f.stem for f in _SUB_MANAGER_PROFILES_DIR.glob("*.yaml")]
                    if profiles:
                        self.ui.print_info(f"Available profiles: {', '.join(profiles)}")
                return True
            name = parts[1]
            profile = parts[2]
            model = parts[3] if len(parts) > 3 else "claude-3-5-sonnet-20241022"
            # Try to get description from profile
            description = ""
            profile_path = _SUB_MANAGER_PROFILES_DIR / f"{profile}.yaml"
            if profile_path.exists():
                try:
                    from .config import load_sub_manager_profile
                    profile_data = load_sub_manager_profile(profile_path)
                    description = profile_data.get("description", "")
                    # Use profile model if user didn't specify
                    if len(parts) <= 3 and profile_data.get("model"):
                        model = profile_data["model"]
                except Exception:
                    pass
            try:
                sm = self.sub_manager_registry.add(name, profile, model, description)
                self.ui.print_success(f"Sub-manager '{sm.name}' added (profile: {profile}, model: {model})")
                self._refresh_manager_tools()
                self._show_submanager_list()
            except ValueError as e:
                self.ui.print_error(str(e))
            return True

        elif sub == "remove":
            if len(parts) < 2:
                self.ui.print_info("Usage: /submanager remove <name>")
                return True
            name = parts[1]
            if self.sub_manager_registry.remove(name):
                self.ui.print_success(f"Sub-manager '{name}' removed")
                self._refresh_manager_tools()
                self._show_submanager_list()
            else:
                self.ui.print_error(f"Sub-manager '{name}' not found")
            return True

        elif sub == "set":
            # /submanager set <name> active|inactive
            if len(parts) < 3:
                self.ui.print_info("Usage: /submanager set <name> active|inactive")
                return True
            name = parts[1]
            state = parts[2].lower()
            if state == "active":
                if self.sub_manager_registry.set_active(name):
                    self._refresh_manager_tools()
                    self.ui.print_success(f"Sub-manager '{name}' is now active")
                    self._show_submanager_list()
                else:
                    self.ui.print_error(f"Sub-manager '{name}' not found")
            elif state in ("inactive", "deactive"):
                if self.sub_manager_registry.set_inactive(name):
                    self._refresh_manager_tools()
                    self.ui.print_success(f"Sub-manager '{name}' is now inactive")
                    self._show_submanager_list()
                else:
                    self.ui.print_error(f"Sub-manager '{name}' not found")
            else:
                self.ui.print_info("Usage: /submanager set <name> active|inactive")
            return True

        elif sub == "show":
            if len(parts) < 2:
                self.ui.print_info("Usage: /submanager show <name>")
                return True
            name = parts[1]
            sm = self.sub_manager_registry.get(name)
            if sm:
                settings_dict = {
                    "Name": sm.name,
                    "Profile": sm.profile,
                    "Model": sm.model,
                    "Description": sm.description or "(none)",
                    "Status": "Active" if sm.active else "Inactive",
                    "Tool": f"consult_{sm.name}",
                    "API Base": sm.api_base or "(from profile)",
                    "API Key": f"****...{sm.api_key[-4:]}" if sm.api_key and len(sm.api_key) > 4 else "(from profile)",
                    "Temperature": str(sm.temperature) if sm.temperature is not None else "(from profile)",
                    "Max Tokens": str(sm.max_tokens) if sm.max_tokens is not None else "(from profile)",
                }
                self.ui.print_settings(settings_dict)
            else:
                self.ui.print_error(f"Sub-manager '{name}' not found")
            return True

        elif sub == "model":
            # /submanager model <name> <model>
            if len(parts) < 3:
                self.ui.print_info("Usage: /submanager model <name> <model>")
                return True
            name = parts[1]
            new_model = parts[2]
            if self.sub_manager_registry.update_model(name, new_model):
                self.ui.print_success(f"Sub-manager '{name}' model changed to: {new_model}")
                self._refresh_manager_tools()
                self._show_submanager_list()
            else:
                self.ui.print_error(f"Sub-manager '{name}' not found")
            return True

        elif sub == "profile":
            # /submanager profile <name> <profile>
            if len(parts) < 3:
                self.ui.print_info("Usage: /submanager profile <name> <profile>")
                # List available profiles
                if _SUB_MANAGER_PROFILES_DIR.exists():
                    profiles = [f.stem for f in _SUB_MANAGER_PROFILES_DIR.glob("*.yaml")]
                    if profiles:
                        self.ui.print_info(f"Available profiles: {', '.join(profiles)}")
                return True
            name = parts[1]
            new_profile = parts[2]
            if self.sub_manager_registry.update_profile(name, new_profile):
                self.ui.print_success(f"Sub-manager '{name}' profile changed to: {new_profile}")
                self._refresh_manager_tools()
                self._show_submanager_list()
            else:
                self.ui.print_error(f"Sub-manager '{name}' not found")
            return True

        elif sub == "api":
            # /submanager api <name> <api_base> [api_key]
            if len(parts) < 3:
                self.ui.print_info("Usage: /submanager api <name> <api_base> [api_key]")
                return True
            name = parts[1]
            api_base = parts[2]
            api_key = parts[3] if len(parts) > 3 else None
            if self.sub_manager_registry.update_api(name, api_base, api_key):
                self.ui.print_success(f"Sub-manager '{name}' API set to: {api_base}")
                self._refresh_manager_tools()
                self._show_submanager_list()
            else:
                self.ui.print_error(f"Sub-manager '{name}' not found")
            return True

        elif sub == "description":
            # /submanager description <name> <description...>
            if len(parts) < 3:
                self.ui.print_info("Usage: /submanager description <name> <description text>")
                return True
            name = parts[1]
            description = " ".join(parts[2:])
            if self.sub_manager_registry.update_description(name, description):
                self.ui.print_success(f"Sub-manager '{name}' description updated")
                self._refresh_manager_tools()
            else:
                self.ui.print_error(f"Sub-manager '{name}' not found")
            return True

        elif sub == "llm":
            return self._handle_submanager_llm_command(" ".join(parts[1:]) if len(parts) > 1 else "")

        else:
            self.ui.print_info("Usage: /submanager <list|add|remove|set|show|model|profile|api|description|llm>")
            return True

    # ================================================================
    # Manager LLM Pool Command Handlers
    # ================================================================

    def _handle_manager_llm_command(self, arg: str) -> bool:
        """Handle /manager llm sub-commands."""
        parts = arg.split()
        sub = parts[0].lower() if parts else "list"

        if sub == "list":
            llms = self.manager.llm_pool.list_all()
            if not llms:
                self.ui.print_info("No parallel LLMs configured for Manager.")
                self.ui.print_info("Use: /manager llm add <name> <model> [api_base] [api_key]")
                return True
            from rich.table import Table
            table = Table(title="Manager Parallel LLMs", show_header=True, header_style="bold magenta")
            table.add_column("Name", style="magenta")
            table.add_column("Model", style="dim")
            table.add_column("API Base", style="dim", max_width=30)
            for cfg in llms:
                table.add_row(cfg.name, cfg.model, cfg.api_base or "(default)")
            self.ui.console.print(table)
            return True

        elif sub == "add":
            # /manager llm add <name> <model> [api_base] [api_key]
            if len(parts) < 3:
                self.ui.print_info("Usage: /manager llm add <name> <model> [api_base] [api_key]")
                self.ui.print_info("Example: /manager llm add gpt4o gpt-4o https://api.openai.com/v1 sk-xxx")
                return True
            name = parts[1]
            model = parts[2]
            api_base = parts[3] if len(parts) > 3 else None
            api_key = parts[4] if len(parts) > 4 else None
            try:
                cfg = self.manager.llm_pool.add(name, model, api_base=api_base, api_key=api_key)
                self.ui.print_success(f"Parallel LLM '{cfg.name}' added (model: {model})")
                self.manager.refresh_system_prompt()
                self._handle_manager_llm_command("list")
            except ValueError as e:
                self.ui.print_error(str(e))
            return True

        elif sub == "remove":
            if len(parts) < 2:
                self.ui.print_info("Usage: /manager llm remove <name>")
                return True
            name = parts[1]
            if self.manager.llm_pool.remove(name):
                self.ui.print_success(f"Parallel LLM '{name}' removed")
                self.manager.refresh_system_prompt()
            else:
                self.ui.print_error(f"Parallel LLM '{name}' not found")
            return True

        elif sub == "set":
            # /manager llm set <name> model <model>
            # /manager llm set <name> api <base> [key]
            if len(parts) < 4:
                self.ui.print_info("Usage: /manager llm set <name> model <model>")
                self.ui.print_info("       /manager llm set <name> api <base> [key]")
                return True
            name = parts[1]
            prop = parts[2].lower()
            if prop == "model":
                if self.manager.llm_pool.update(name, model=parts[3]):
                    self.ui.print_success(f"Parallel LLM '{name}' model changed to: {parts[3]}")
                    self.manager.refresh_system_prompt()
                else:
                    self.ui.print_error(f"Parallel LLM '{name}' not found")
            elif prop == "api":
                kwargs = {"api_base": parts[3]}
                if len(parts) > 4:
                    kwargs["api_key"] = parts[4]
                if self.manager.llm_pool.update(name, **kwargs):
                    self.ui.print_success(f"Parallel LLM '{name}' API updated")
                else:
                    self.ui.print_error(f"Parallel LLM '{name}' not found")
            else:
                self.ui.print_info("Usage: /manager llm set <name> model|api <value>")
            return True

        else:
            self.ui.print_info("Usage: /manager llm <list|add|remove|set>")
            self.ui.print_info("")
            self.ui.print_info("Examples:")
            self.ui.print_info("  /manager llm list")
            self.ui.print_info("  /manager llm add gpt4o gpt-4o https://api.openai.com/v1 sk-xxx")
            self.ui.print_info("  /manager llm remove gpt4o")
            self.ui.print_info("  /manager llm set gpt4o model gpt-4-turbo")
            self.ui.print_info("  /manager llm set gpt4o api https://new-api.com sk-yyy")
            return True

    # ================================================================
    # Sub-Manager LLM Pool Command Handlers
    # ================================================================

    def _handle_submanager_llm_command(self, arg: str) -> bool:
        """Handle /submanager llm sub-commands."""
        parts = arg.split()
        if len(parts) < 1:
            self.ui.print_info("Usage: /submanager llm <sm_name> <list|add|remove>")
            return True

        sm_name = parts[0]
        sm = self.sub_manager_registry.get(sm_name)
        if not sm:
            self.ui.print_error(f"Sub-manager '{sm_name}' not found")
            return True

        sub = parts[1].lower() if len(parts) > 1 else "list"

        if sub == "list":
            llms = self.sub_manager_registry.list_parallel_llms(sm_name)
            if not llms:
                self.ui.print_info(f"No parallel LLMs configured for sub-manager '{sm_name}'.")
                self.ui.print_info(f"Use: /submanager llm {sm_name} add <name> <model> [api_base] [api_key]")
                return True
            from rich.table import Table
            table = Table(title=f"Parallel LLMs for '{sm_name}'", show_header=True, header_style="bold magenta")
            table.add_column("Name", style="magenta")
            table.add_column("Model", style="dim")
            table.add_column("API Base", style="dim", max_width=30)
            for llm in llms:
                table.add_row(llm.get("name", "?"), llm.get("model", "?"), llm.get("api_base", "(default)"))
            self.ui.console.print(table)
            return True

        elif sub == "add":
            # /submanager llm <sm> add <name> <model> [api_base] [api_key]
            if len(parts) < 4:
                self.ui.print_info(f"Usage: /submanager llm {sm_name} add <name> <model> [api_base] [api_key]")
                return True
            llm_name = parts[2]
            model = parts[3]
            api_base = parts[4] if len(parts) > 4 else None
            api_key = parts[5] if len(parts) > 5 else None
            if self.sub_manager_registry.add_parallel_llm(sm_name, llm_name, model, api_base, api_key):
                self.ui.print_success(f"Parallel LLM '{llm_name}' added to sub-manager '{sm_name}'")
                self._handle_submanager_llm_command(f"{sm_name} list")
            else:
                self.ui.print_error(f"Failed to add LLM '{llm_name}' (may already exist)")
            return True

        elif sub == "remove":
            if len(parts) < 3:
                self.ui.print_info(f"Usage: /submanager llm {sm_name} remove <name>")
                return True
            llm_name = parts[2]
            if self.sub_manager_registry.remove_parallel_llm(sm_name, llm_name):
                self.ui.print_success(f"Parallel LLM '{llm_name}' removed from sub-manager '{sm_name}'")
            else:
                self.ui.print_error(f"Parallel LLM '{llm_name}' not found in sub-manager '{sm_name}'")
            return True

        else:
            self.ui.print_info(f"Usage: /submanager llm {sm_name} <list|add|remove>")
            return True

    # ================================================================
    # Team Command Handlers
    # ================================================================

    def _show_team_list(self):
        """Display the team list table."""
        teams = self.team_registry.list_all()
        if not teams:
            self.ui.print_info("No teams configured. Use /team add <name> <manager_profile> [sub_manager1,sub_manager2,...]")
            return True
        from rich.table import Table
        table = Table(title="Teams", show_header=True, header_style="bold cyan")
        table.add_column("Name", style="green")
        table.add_column("Manager Profile", style="dim")
        table.add_column("Sub-Managers", style="dim", max_width=40)
        table.add_column("Description", style="dim", max_width=30)
        table.add_column("Status", style="bold")
        for tc in teams:
            status = "[green]active *[/green]" if tc.active else "[dim]inactive[/dim]"
            sm_names = ", ".join(tc.sub_manager_names) if tc.sub_manager_names else "(none)"
            table.add_row(tc.name, tc.main_manager_profile, sm_names, tc.description or "", status)
        self.ui.console.print(table)
        return True

    def _handle_team_command(self, arg: str):
        """Handle /team sub-commands."""
        parts = arg.split()
        sub = parts[0].lower() if parts else ""

        if sub == "list" or not sub:
            self._show_team_list()
            return True

        elif sub == "add":
            # /team add <name> <manager_profile> [sub_manager1,sub_manager2,...]
            if len(parts) < 3:
                self.ui.print_info("Usage: /team add <name> <manager_profile> [sub_manager1,sub_manager2,...]")
                self.ui.print_info("Example: /team add review-team default architect,security")
                return True
            name = parts[1]
            manager_profile = parts[2]
            sm_names = parts[3].split(",") if len(parts) > 3 else []
            # Validate sub-manager names
            for sm_name in sm_names:
                if not self.sub_manager_registry.get(sm_name):
                    self.ui.print_error(f"Sub-manager '{sm_name}' not found in registry")
                    return True
            try:
                tc = self.team_registry.add(name, manager_profile, sm_names)
                self.ui.print_success(f"Team '{tc.name}' created (manager: {manager_profile}, sub-managers: {', '.join(sm_names) or 'none'})")
                self._show_team_list()
            except ValueError as e:
                self.ui.print_error(str(e))
            return True

        elif sub == "remove":
            if len(parts) < 2:
                self.ui.print_info("Usage: /team remove <name>")
                return True
            name = parts[1]
            if self.team_registry.remove(name):
                self.ui.print_success(f"Team '{name}' removed")
                self._show_team_list()
            else:
                self.ui.print_error(f"Team '{name}' not found")
            return True

        elif sub == "activate":
            if len(parts) < 2:
                self.ui.print_info("Usage: /team activate <name>")
                return True
            name = parts[1]
            tc = self.team_registry.get(name)
            if not tc:
                self.ui.print_error(f"Team '{name}' not found")
                return True

            # 1. Activate team (deactivates others)
            self.team_registry.activate(name)

            # 2. Change Main Manager profile
            profiles_dir = Path(__file__).parent / "manager_profiles"
            profile_path = profiles_dir / f"{tc.main_manager_profile}.yaml"
            if profile_path.exists():
                try:
                    write_env_value("MANAGER_PROFILE", tc.main_manager_profile)
                    reload_settings()
                    self.settings = get_settings()
                except Exception as e:
                    self.ui.print_warning(f"Failed to set manager profile: {e}")

            # 3. Activate only team's sub-managers
            self.sub_manager_registry.activate_only(tc.sub_manager_names)

            # 4. Reinitialize manager
            self._init_manager()
            self._refresh_manager_tools()

            sm_list = ", ".join(tc.sub_manager_names) if tc.sub_manager_names else "(none)"
            self.ui.print_success(
                f"Team '{name}' activated\n"
                f"  Manager profile: {tc.main_manager_profile}\n"
                f"  Active sub-managers: {sm_list}"
            )
            return True

        elif sub == "deactivate":
            self.team_registry.deactivate()
            self.ui.print_success("All teams deactivated. Sub-managers retain their individual active/inactive state.")
            return True

        elif sub == "show":
            if len(parts) < 2:
                self.ui.print_info("Usage: /team show <name>")
                return True
            name = parts[1]
            tc = self.team_registry.get(name)
            if tc:
                settings_dict = {
                    "Name": tc.name,
                    "Manager Profile": tc.main_manager_profile,
                    "Sub-Managers": ", ".join(tc.sub_manager_names) if tc.sub_manager_names else "(none)",
                    "Description": tc.description or "(none)",
                    "Status": "Active" if tc.active else "Inactive",
                }
                self.ui.print_settings(settings_dict)
            else:
                self.ui.print_error(f"Team '{name}' not found")
            return True

        elif sub == "addmember":
            # /team addmember <team_name> <sub_manager_name>
            if len(parts) < 3:
                self.ui.print_info("Usage: /team addmember <team_name> <sub_manager_name>")
                return True
            team_name = parts[1]
            sm_name = parts[2]
            if not self.sub_manager_registry.get(sm_name):
                self.ui.print_error(f"Sub-manager '{sm_name}' not found")
                return True
            if self.team_registry.add_sub_manager(team_name, sm_name):
                self.ui.print_success(f"Sub-manager '{sm_name}' added to team '{team_name}'")
                tc = self.team_registry.get(team_name)
                if tc and tc.active:
                    self.sub_manager_registry.activate_only(tc.sub_manager_names)
                    self._refresh_manager_tools()
            else:
                self.ui.print_error(f"Team '{team_name}' not found")
            return True

        elif sub == "removemember":
            # /team removemember <team_name> <sub_manager_name>
            if len(parts) < 3:
                self.ui.print_info("Usage: /team removemember <team_name> <sub_manager_name>")
                return True
            team_name = parts[1]
            sm_name = parts[2]
            if self.team_registry.remove_sub_manager(team_name, sm_name):
                self.ui.print_success(f"Sub-manager '{sm_name}' removed from team '{team_name}'")
                tc = self.team_registry.get(team_name)
                if tc and tc.active:
                    self.sub_manager_registry.activate_only(tc.sub_manager_names)
                    self._refresh_manager_tools()
            else:
                self.ui.print_error(f"Team '{team_name}' not found or sub-manager not a member")
            return True

        elif sub == "manager":
            # /team manager <team_name> <profile>
            if len(parts) < 3:
                self.ui.print_info("Usage: /team manager <team_name> <profile>")
                return True
            team_name = parts[1]
            profile = parts[2]
            if self.team_registry.update_main_manager(team_name, profile):
                self.ui.print_success(f"Team '{team_name}' manager profile changed to: {profile}")
                tc = self.team_registry.get(team_name)
                if tc and tc.active:
                    # Re-activate to apply new profile
                    self._handle_team_command(f"activate {team_name}")
            else:
                self.ui.print_error(f"Team '{team_name}' not found")
            return True

        else:
            self.ui.print_info("Usage: /team <list|add|remove|activate|deactivate|show|addmember|removemember|manager>")
            return True


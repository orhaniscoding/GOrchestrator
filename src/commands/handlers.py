"""
Command Handlers - Command handlers.

Separate handler for each source (manager, worker, session, system, mode).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.engine import SessionEngine


class CommandHandler:
    """Command handlers."""

    def __init__(self, engine: "SessionEngine"):
        """Initialize the handler."""
        self.engine = engine

    def handle(self, cmd) -> bool:
        """
        Processes the command.

        Args:
            cmd: Command object (from parser.py)

        Returns:
            True on success, False on error
        """
        match cmd.source:
            case "manager":
                return self._handle_manager(cmd)
            case "worker":
                return self._handle_worker(cmd)
            case "session":
                return self._handle_session(cmd)
            case "system":
                return self._handle_system(cmd)
            case "mode":
                return self._handle_mode(cmd)
            case "submanager":
                return self._handle_submanager(cmd)
            case "team":
                return self._handle_team(cmd)
            case _:
                self.engine.ui.print_error(f"Unknown command source: {cmd.source}")
                return False

    # ================================================================
    # Manager Handlers
    # ================================================================

    def _handle_manager(self, cmd) -> bool:
        """Handles manager commands."""
        action = cmd.action.lower()

        if action == "show":
            return self._manager_show()
        elif action == "set profile":
            return self._manager_set_profile(cmd.args)
        elif action == "set model":
            return self._manager_set_model(cmd.args, cmd.options)
        elif action == "set api":
            return self._manager_set_api(cmd.args, cmd.options)
        elif action == "set prompt":
            return self._manager_set_prompt(cmd.args)
        elif action in (
            "llm", "rules", "temp", "tokens", "model", "api",
            "prompt", "profile", "list",
        ):
            # Delegate to engine's comprehensive manager command handler
            full_cmd = action + (" " + " ".join(cmd.args) if cmd.args else "")
            return self.engine._handle_manager_command(full_cmd)
        else:
            self.engine.ui.print_error(f"Unknown manager action: {action}")
            self.engine.ui.print_info(
                "Usage: /manager show|set profile|set model|set api|set prompt"
                "|llm|rules|temp|tokens|model|api|prompt|profile|list"
            )
            return False

    def _manager_show(self) -> bool:
        """Show manager settings."""
        # Use existing handler
        return self.engine._manager_show_config()

    def _manager_set_profile(self, args: list[str]) -> bool:
        """Change manager profile."""
        if len(args) < 1:
            self.engine.ui.print_error("Usage: /manager set profile <name>")
            return False

        profile_name = args[0]
        return self.engine._manager_set_profile(profile_name)

    def _manager_set_model(self, args: list[str], options: dict) -> bool:
        """Change manager model."""
        if len(args) < 1:
            self.engine.ui.print_error("Usage: /manager set model <name> [--global]")
            return False

        model_name = args[0]
        persistent = "--global" in options
        return self.engine._manager_set_model(model_name, persistent=persistent)

    def _manager_set_api(self, args: list[str], options: dict) -> bool:
        """Change manager API settings."""
        if len(args) < 1:
            self.engine.ui.print_error("Usage: /manager set api <base> [key] [--global]")
            return False

        api_base = args[0]
        api_key = args[1] if len(args) > 1 else None
        persistent = "--global" in options
        return self.engine._manager_set_api(api_base, api_key, persistent=persistent)

    def _manager_set_prompt(self, args: list[str]) -> bool:
        """Change manager system prompt."""
        prompt_text = " ".join(args)
        if not prompt_text:
            self.engine.ui.print_error("Usage: /manager set prompt <text>")
            return False

        return self.engine._manager_set_prompt(prompt_text)

    # ================================================================
    # Worker Handlers
    # ================================================================

    def _handle_worker(self, cmd) -> bool:
        """Handles worker commands."""
        action = cmd.action.lower()
        # Reconstruct full action string with args for sub-handlers
        full_action = action + (" " + " ".join(cmd.args) if cmd.args else "")

        if action == "list":
            return self._worker_list()
        elif action.startswith("show"):
            return self._worker_show(full_action)
        elif action.startswith("add"):
            # Parse action (e.g.: "add coder gemini-pro live")
            return self._worker_add(full_action)
        elif action.startswith("remove"):
            # Parse action (e.g.: "remove coder")
            return self._worker_remove(full_action)
        elif action.startswith("set"):
            return self._worker_set(full_action)
        else:
            self.engine.ui.print_error(f"Unknown worker action: {action}")
            self.engine.ui.print_info("Usage: /worker list|add|remove|show|set")
            return False

    def _worker_list(self) -> bool:
        """Show worker list."""
        return self.engine._show_worker_list()

    def _worker_show(self, action: str) -> bool:
        """Show worker details."""
        # Parse action (e.g.: "show default")
        parts = action.split()
        if len(parts) < 2:
            self.engine.ui.print_error("Usage: /worker show <name>")
            return False

        # Show worker details (basic implementation)
        worker_name = parts[1]
        wc = self.engine.worker_registry.get(worker_name)
        if not wc:
            self.engine.ui.print_error(f"Worker '{worker_name}' not found")
            return False

        from rich.table import Table
        table = Table(title=f"Worker: {worker_name}")
        table.add_column("Setting", style="green")
        table.add_column("Value", style="cyan")

        table.add_row("Name", wc.name)
        table.add_row("Model", wc.model)
        table.add_row("Profile", wc.profile)
        table.add_row("API Base", wc.api_base or "default")
        api_key_display = f"****...{wc.api_key[-4:]}" if wc.api_key and len(wc.api_key) > 4 else wc.api_key or "default"
        table.add_row("API Key", api_key_display)
        table.add_row("Tool", f"delegate_to_{wc.name}")
        table.add_row("Status", "active" if wc.active else "inactive")

        self.engine.ui.console.print(table)
        return True

    def _worker_add(self, action: str) -> bool:
        """Add new worker."""
        # Parse action (e.g.: "add coder gemini-pro live" -> ["coder", "gemini-pro", "live"])
        parts = action.split()
        if len(parts) < 2:
            self.engine.ui.print_error("Usage: /worker add <name> [model] [profile]")
            return False

        # Use existing _handle_worker_command
        # Note: parts[0] = "add", parts[1] = name, parts[2] = model, parts[3] = profile
        cmd_str = "add " + " ".join(parts[1:])
        return self.engine._handle_worker_command(cmd_str)

    def _worker_remove(self, action: str) -> bool:
        """Remove worker."""
        # Parse action (e.g.: "remove coder" -> ["coder"])
        parts = action.split()
        if len(parts) < 2:
            self.engine.ui.print_error("Usage: /worker remove <name>")
            return False

        return self.engine._handle_worker_command(f"remove {parts[1]}")

    def _worker_set(self, action: str) -> bool:
        """Change worker settings."""
        # Parse action (e.g.: "set second active")
        parts = action.split()
        if len(parts) < 3:
            self.engine.ui.print_error("Usage: /worker set <name> <action> [args]")
            self.engine.ui.print_info("Actions: active, inactive, primary, model, api, profile")
            return False

        worker_name = parts[1]
        action_type = parts[2].lower()

        if action_type in ("active", "inactive", "primary"):
            return self.engine._handle_worker_command(f"set {worker_name} {action_type}")
        elif action_type == "model" and len(parts) >= 4:
            return self.engine._handle_worker_command(f"model {worker_name} {parts[3]}")
        elif action_type == "profile" and len(parts) >= 4:
            return self.engine._handle_worker_command(f"profile {worker_name} {parts[3]}")
        elif action_type == "api" and len(parts) >= 4:
            api_base = parts[3]
            api_key = parts[4] if len(parts) > 4 else None
            return self.engine._handle_worker_command(f"api {worker_name} {api_base} {api_key or ''}")
        else:
            self.engine.ui.print_error(f"Unknown worker action: {action_type}")
            return False

    # ================================================================
    # Session Handlers
    # ================================================================

    def _handle_session(self, cmd) -> bool:
        """Handles session commands."""
        action = cmd.action.lower()

        if action == "list":
            return self._session_list()
        elif action == "show":
            return self._session_show()
        elif action.startswith("save"):
            return self._session_save(cmd.args)
        elif action.startswith("new"):
            return self._session_new(cmd.args)
        elif action.startswith("load"):
            return self._session_load(cmd.args)
        elif action.startswith("export"):
            return self._session_export(cmd.args)
        else:
            self.engine.ui.print_error(f"Unknown session action: {action}")
            self.engine.ui.print_info("Usage: /session list|show|save|new|load")
            return False

    def _session_list(self) -> bool:
        """Show session list."""
        from datetime import datetime
        sessions = self.engine.list_sessions()
        if sessions:
            from rich.table import Table
            table = Table(title="Saved Sessions", show_header=True, header_style="bold cyan")
            table.add_column("ID", style="dim", max_width=22)
            table.add_column("Name", style="green")
            table.add_column("Saved At", style="dim")
            table.add_column("Messages", style="cyan", justify="right")
            table.add_column("Summary", style="dim", overflow="fold")
            active_id = self.engine.session_id or ""
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
            self.engine.ui.console.print(table)
            if active_id:
                self.engine.ui.print_info(f"Active session: {active_id} (*)")
        else:
            self.engine.ui.print_info("No saved sessions found.")
        return True

    def _session_show(self) -> bool:
        """Show current session info."""
        self.engine.ui.print_info(f"Session: {self.engine.session_name}")
        self.engine.ui.print_info(f"Session ID: {self.engine.session_id}")
        msg_count = len(self.engine.manager.messages) - 1 if self.engine.manager else 0
        self.engine.ui.print_info(f"Messages: {msg_count}")
        return True

    def _session_save(self, args: list[str]) -> bool:
        """Save session."""
        name = args[0] if len(args) >= 1 else None
        try:
            self.engine.save_session(name)
            display_name = name or self.engine.session_name
            self.engine.ui.print_success(f"Session saved: {display_name} (ID: {self.engine.session_id})")
            return True
        except Exception as e:
            self.engine.ui.print_error(f"Failed to save: {e}")
            return False

    def _session_new(self, args: list[str]) -> bool:
        """New session."""
        name = args[0] if len(args) >= 1 else ""
        self.engine._auto_save()
        self.engine._new_session(name)
        if self.engine.manager:
            self.engine.manager.clear_history()
        else:
            self.engine._init_manager()
        self.engine.ui.print_success(f"New session started: {self.engine.session_name} (ID: {self.engine.session_id})")
        return True

    def _session_load(self, args: list[str]) -> bool:
        """Load session."""
        if len(args) < 1:
            self.engine.ui.print_error("Usage: /session load <id|name>")
            return False

        identifier = args[0]
        if self.engine.load_session(identifier):
            msg_count = len(self.engine.manager.messages) - 1 if self.engine.manager else 0
            self.engine.ui.print_success(f"Session '{self.engine.session_name}' loaded ({msg_count} messages)")
            return True
        else:
            self.engine.ui.print_error(f"Session '{identifier}' not found.")
            return False

    def _session_export(self, args: list[str]) -> bool:
        """Export session."""
        if len(args) < 1:
            self.engine.ui.print_error("Usage: /session export <filename>")
            return False

        # Session export (basic implementation - no existing command)
        filename = args[0]
        self.engine.ui.print_warning("Session export not yet implemented.")
        return False

    # ================================================================
    # System Handlers
    # ================================================================

    def _handle_system(self, cmd) -> bool:
        """Handles system commands."""
        action = cmd.action.lower()

        if action == "show":
            return self._system_show()
        elif action == "validate":
            return self._system_validate()
        elif action == "reload":
            return self._system_reload()
        elif action == "reset":
            return self._system_reset()
        else:
            self.engine.ui.print_error(f"Unknown system action: {action}")
            self.engine.ui.print_info("Usage: /system show|validate|reload")
            return False

    def _system_show(self) -> bool:
        """Show system status."""
        # Use /config show command (deprecated but still works)
        # Basic status display for the new system
        self.engine.ui.print_info("System Status:")
        self.engine.ui.print_info(f"  Manager Model: {self.engine.settings.ORCHESTRATOR_MODEL}")
        self.engine.ui.print_info(f"  Worker Model: {self.engine.settings.WORKER_MODEL}")
        self.engine.ui.print_info(f"  Mode: {'Verbose' if self.engine.ui.verbose_worker else 'Quiet'}")
        self.engine.ui.print_info(f"  Confirm: {'ON' if self.engine._confirm_mode else 'OFF'}")
        return True

    def _system_validate(self) -> bool:
        """Validate settings."""
        issues = self.engine.settings.validate_config()
        if not issues:
            self.engine.ui.print_success("Configuration is valid. No issues found.")
            return True
        else:
            for issue in issues:
                if issue["level"] == "error":
                    self.engine.ui.print_error(f"{issue['message']}")
                else:
                    self.engine.ui.print_warning(f"{issue['message']}")
            return False

    def _system_reload(self) -> bool:
        """Reload settings from .env."""
        from ..core.config import reload_settings, write_env_value

        try:
            self.engine.settings = reload_settings(clear_overrides=True)

            # Pass new settings to manager
            if self.engine.manager:
                self.engine.manager.settings = self.engine.settings
                self.engine.manager.worker.settings = self.engine.settings

            self.engine.ui.verbose_worker = self.engine.settings.VERBOSE_WORKER

            # Sync worker registry
            primary = self.engine.worker_registry.get_primary()
            if primary:
                self.engine.worker_registry.update_model(primary.name, self.engine.settings.WORKER_MODEL)
                self.engine.worker_registry.update_profile(primary.name, self.engine.settings.WORKER_PROFILE)

            self.engine._refresh_manager_tools()
            self.engine.ui.print_success("Configuration reloaded from .env")
            return True
        except Exception as e:
            self.engine.ui.print_error(f"Failed to reload config: {e}")
            return False

    def _system_reset(self) -> bool:
        """Reset settings."""
        self.engine.ui.print_warning("System reset not yet implemented.")
        return False

    # ================================================================
    # Mode Handlers
    # ================================================================

    def _handle_mode(self, cmd) -> bool:
        """Handles mode commands."""
        action = cmd.action.lower()

        if action == "verbose":
            return self._mode_verbose()
        elif action == "quiet":
            return self._mode_quiet()
        elif action.startswith("confirm on"):
            return self._mode_confirm(True)
        elif action.startswith("confirm off"):
            return self._mode_confirm(False)
        else:
            self.engine.ui.print_error(f"Unknown mode action: {action}")
            self.engine.ui.print_info("Usage: /mode verbose|quiet|confirm on|confirm off")
            return False

    # ================================================================
    # Sub-Manager Handlers
    # ================================================================

    def _handle_submanager(self, cmd) -> bool:
        """Handles sub-manager commands. Delegates to engine."""
        action = cmd.action.lower()
        full_cmd = action + (" " + " ".join(cmd.args) if cmd.args else "")
        return self.engine._handle_submanager_command(full_cmd)

    # ================================================================
    # Team Handlers
    # ================================================================

    def _handle_team(self, cmd) -> bool:
        """Handles team commands. Delegates to engine."""
        action = cmd.action.lower()
        full_cmd = action + (" " + " ".join(cmd.args) if cmd.args else "")
        return self.engine._handle_team_command(full_cmd)

    # ================================================================
    # Mode Handlers (continued)
    # ================================================================

    def _mode_verbose(self) -> bool:
        """Verbose mode."""
        self.engine.ui.verbose_worker = True
        self.engine.ui.print_success("Verbose mode enabled. Worker output will be shown in detail.")
        return True

    def _mode_quiet(self) -> bool:
        """Quiet mode."""
        self.engine.ui.verbose_worker = False
        self.engine.ui.print_success("Quiet mode enabled. Worker output will be summarized.")
        return True

    def _mode_confirm(self, on: bool) -> bool:
        """Confirm mode."""
        self.engine._confirm_mode = on
        status = "ON" if on else "OFF"
        self.engine.ui.print_success(f"Confirm mode {status}.")
        return True

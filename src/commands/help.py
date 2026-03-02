"""
Help System - Help system.

Main help and detailed help screens.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.engine import SessionEngine


class HelpSystem:
    """Help system."""

    def __init__(self, engine: "SessionEngine"):
        """Initialize the help system."""
        self.engine = engine

    def show_main_help(self):
        """Show main help screen."""
        from rich.panel import Panel
        from rich.console import Group
        from rich.text import Text

        # Main help text
        help_text = """
╭─────────────────────────────────────────────────────────────────────────────╮
│                        GOrchestrator Command Reference                  │
╰─────────────────────────────────────────────────────────────────────────────╯

📋 Quick Commands:
  /manager show         Show manager configuration
  /worker list          List all workers
  /session list         List all sessions
  /system validate      Validate configuration

📚 Command Groups:

  /manager  → Manager settings
    show                 : Show current settings
    set profile <name>  : Change profile
    set model <name>    : Change model [persist to .env with --global]
    set api <base> [key] : Set API
    llm list             : List parallel LLMs
    llm add <name> <model> [api_base] [api_key] : Add parallel LLM
    llm remove <name>    : Remove parallel LLM
    llm set <name> model|api <value> : Change parallel LLM settings

  /worker   → Worker management
    list                 : List workers
    add <name> [model] : Add new worker
    remove <name>      : Remove worker
    set <name> active|inactive|primary : Set status
    set <name> model|api|profile <value> : Change setting

  /submanager (/sm) → Expert Advisor management (Mixture of Agents)
    list                 : List sub-managers
    add <name> <profile> [model] : Add new sub-manager
    remove <name>      : Remove sub-manager
    set <name> active|inactive : Set status
    show <name>        : Sub-manager details
    model <name> <model> : Change model
    profile <name> <profile> : Change profile
    api <name> <base> [key] : Set API
    description <name> <text> : Change description
    llm <name> list    : List parallel LLMs
    llm <name> add <llm> <model> [api_base] [api_key] : Add parallel LLM
    llm <name> remove <llm> : Remove parallel LLM

  /team     → Team management (Manager + Sub-Manager combination)
    list                 : List teams
    add <name> <profile> [sm1,sm2,...] : Create team
    remove <name>      : Remove team
    activate <name>    : Activate team (profile + sub-managers are configured)
    deactivate         : Deactivate all teams
    show <name>        : Team details
    addmember <team> <sm> : Add sub-manager
    removemember <team> <sm> : Remove sub-manager
    manager <team> <profile> : Change manager profile

  /session  → Session management
    list                 : List sessions
    save [name]         : Save session
    new [name]          : New session
    load <id|name>      : Load session
    export <file>       : Export [planned]

  /system   → System settings
    show                 : System status
    validate            : Validate settings
    reload              : Reload settings
    reset               : Reset settings [planned]

  /mode     → Mode settings
    verbose|quiet       : Output mode
    confirm on|off      : Confirmation mode

💡 Tips:
  - Tab key auto-completion
  - Use --global to persist settings to .env
  - /help <command> for detailed command info

Examples:
  /manager set model anthropic/claude-opus-4 --global
  /manager llm add gpt4o gpt-4o https://api.openai.com/v1 sk-xxx
  /manager llm list
  /worker add coder claude-opus-4
  /submanager add architect architect
  /submanager set architect active
  /submanager llm architect add gemini gemini-2.0-flash
  /team add review-team default architect,security
  /team activate review-team
  /session save "Bug Fix"
  /mode verbose
"""

        panel = Panel(help_text, title="Command Reference", border_style="cyan")
        self.engine.ui.console.print(panel)

    def show_command_help(self, command: str):
        """
        Detailed help for a command.

        Args:
            command: Command (e.g.: "/manager set model")
        """
        command = command.strip()
        if not command.startswith("/"):
            self.engine.ui.print_error("Invalid command. Use /help for main help.")
            return False

        # Parse
        from .parser import CommandParser
        parser = CommandParser()
        cmd = parser.parse(command)

        if not cmd:
            self.engine.ui.print_error(f"Unknown command: {command}")
            return False

        # Show command documentation
        self._show_command_doc(cmd)
        return True

    def _show_command_doc(self, cmd):
        """Show command documentation."""
        from rich.panel import Panel

        source = cmd.source.capitalize()
        action = cmd.action

        # Documentation
        doc = self._get_command_doc(source, action)

        panel = Panel(doc, title=f"Command: /{cmd.source} {cmd.action}", border_style="cyan")
        self.engine.ui.console.print(panel)

    def _get_command_doc(self, source: str, action: str) -> str:
        """
        Returns command documentation.

        Args:
            source: Source (manager, worker, etc.)
            action: Action (show, set model, etc.)

        Returns:
            Documentation string
        """
        # Manager documentation
        if source == "Manager":
            return self._get_manager_doc(action)
        elif source == "Worker":
            return self._get_worker_doc(action)
        elif source == "Session":
            return self._get_session_doc(action)
        elif source == "System":
            return self._get_system_doc(action)
        elif source == "Mode":
            return self._get_mode_doc(action)
        else:
            return "No documentation available."

    def _get_manager_doc(self, action: str) -> str:
        """Manager documentation."""
        if action == "show":
            return """
📖 Description:
  Show current manager settings.

⚙️  Usage:
  /manager show

📝 Notes:
  - This command lists all manager settings.
  - Session-based changes (without --global) are shown.
"""
        elif action.startswith("set profile"):
            return """
📖 Description:
  Change manager profile.

⚙️  Usage:
  /manager set profile <profile-name>

📋 Arguments:
  <profile-name>    Profile name (default, advanced, custom, minimal)

📝 Notes:
  - Profile is loaded from a YAML file.
  - src/core/manager_profiles/<profile-name>.yaml

💡 Available Profiles:
  default     : Standard GOrchestrator Manager
  advanced    : Enhanced system prompt
  custom      : Custom configuration
  minimal     : Lightweight for quick tasks
"""
        elif action.startswith("set model"):
            return """
📖 Description:
  Change manager model.

⚙️  Usage:
  /manager set model <model-name> [--global]

📋 Arguments:
  <model-name>    Model name (e.g.: anthropic/claude-opus-4)

🔧 Options:
  --global         Persist setting to .env file
                   (Default: session-based, current session only)

📝 Examples:
  # Session-only (current session only)
  /manager set model anthropic/claude-opus-4

  # Global (persist to .env)
  /manager set model anthropic/claude-opus-4 --global

💡 Related Commands:
  /manager show              → Show current settings
  /manager set api <base>    → Change API settings
  /manager set profile <name> → Change profile

🔍 Available Models:
  anthropic/claude-opus-4
  anthropic/claude-3.5-sonnet
  anthropic/glm-4.7
  gemini/gemini-2.0-pro
"""
        elif action.startswith("set api"):
            return """
📖 Description:
  Change manager API settings.

⚙️  Usage:
  /manager set api <api-base> [api-key] [--global]

📋 Arguments:
  <api-base>       API base URL (e.g.: https://api.z.ai/api/paas/v4/)
  [api-key]        Optional API key

🔧 Options:
  --global         Persist setting to .env file

📝 Examples:
  # Session-only (current session only)
  /manager set api https://api.z.ai/api/paas/v4/

  # Global (persist to .env)
  /manager set api https://api.z.ai/api/paas/v4/ sk-xxx --global

💡 Related Commands:
  /manager show              → Show current settings
  /manager set model <name>  → Change model settings
"""
        elif action.startswith("set prompt"):
            return """
📖 Description:
  Change manager system prompt.

⚙️  Usage:
  /manager set prompt <prompt-text>

📋 Arguments:
  <prompt-text>    System prompt text

📝 Notes:
  - This setting only applies to the current session.
  - Use profile YAML files for permanent changes.

💡 Related Commands:
  /manager set profile <name> → Change profile
"""
        else:
            return f"No documentation for manager action: {action}"

    def _get_worker_doc(self, action: str) -> str:
        """Worker documentation."""
        if action == "list":
            return """
📖 Description:
  List current workers.

⚙️  Usage:
  /worker list

📝 Notes:
  - All registered workers are shown.
  - Active and inactive statuses are shown.
"""
        elif action.startswith("add"):
            return """
📖 Description:
  Add new worker.

⚙️  Usage:
  /worker add <name> [model] [profile]

📋 Arguments:
  <name>            Worker name (required)
  [model]           Worker model (optional)
  [profile]         Worker profile (optional)

📝 Examples:
  /worker add coder claude-opus-4
  /worker add test anthropic/glm-4.7 minimal

💡 Related Commands:
  /worker list        → List workers
  /worker remove <name> → Remove worker
"""
        elif action.startswith("remove"):
            return """
📖 Description:
  Remove worker.

⚙️  Usage:
  /worker remove <name>

📋 Arguments:
  <name>        Worker name

📝 Notes:
  - Worker cannot be used after removal.
  - Primary worker cannot be removed.

💡 Related Commands:
  /worker list        → List workers
  /worker add <name>  → Add new worker
"""
        elif action.startswith("show"):
            return """
📖 Description:
  Show worker details.

⚙️  Usage:
  /worker show <name>

📋 Arguments:
  <name>        Worker name

💡 Related Commands:
  /worker list        → List workers
"""
        elif action.startswith("set"):
            return """
📖 Description:
  Change worker settings.

⚙️  Usage:
  /worker set <name> <action> [args]

📋 Actions:
  active          Activate worker
  inactive        Deactivate worker
  primary         Set as primary worker
  model <val>     Change worker model
  profile <val>   Change worker profile
  api <base> [key] : Set worker API

📝 Examples:
  /worker set coder active
  /worker set coder primary
  /worker set coder model anthropic/glm-4.7
  /worker set coder api https://api.z.ai/api/paas/v4/

💡 Related Commands:
  /worker list        → List workers
  /worker show <name>  → Show worker details
"""
        else:
            return f"No documentation for worker action: {action}"

    def _get_session_doc(self, action: str) -> str:
        """Session documentation."""
        if action == "list":
            return """
📖 Description:
  Lists sessions.

⚙️  Usage:
  /session list

📝 Notes:
  - All saved sessions are shown.
  - ID, name, created, modified info is shown.
"""
        elif action == "show":
            return """
📖 Description:
  Show current session info.

⚙️  Usage:
  /session show

💡 Related Commands:
  /session list        → List sessions
  /session save <name> → Save session
"""
        elif action.startswith("save"):
            return """
📖 Description:
  Save session.

⚙️  Usage:
  /session save [name]

📋 Arguments:
  [name]      Optional name (default: session_name)

📝 Notes:
  - Session is saved automatically.
  - Use this command to save manually.

💡 Related Commands:
  /session list        → List sessions
  /session new <name>  → New session
"""
        elif action.startswith("new"):
            return """
📖 Description:
  Creates a new session.

⚙️  Usage:
  /session new [name]

📋 Arguments:
  [name]      Optional name (default: random)

📝 Notes:
  - Current session is saved automatically.
  - A new session is created.

💡 Related Commands:
  /session list        → List sessions
  /session save <name> → Save session
"""
        elif action.startswith("load"):
            return """
📖 Description:
  Loads a session.

⚙️  Usage:
  /session load <id|name>

📋 Arguments:
  <id|name>    Session ID or name

📝 Notes:
  - Current session is saved automatically.
  - Selected session is loaded.

💡 Related Commands:
  /session list        → List sessions
  /session new <name>  → New session
"""
        elif action.startswith("export"):
            return """
📖 Description:
  Exports session (JSON).

⚙️  Usage:
  /session export <filename>

📝 Notes:
  - Planned for future implementation.
  - Not yet available.

💡 Related Commands:
  /session list        → List sessions
  /session save <name> → Save session
"""
        else:
            return f"No documentation for session action: {action}"

    def _get_system_doc(self, action: str) -> str:
        """System documentation."""
        if action == "show":
            return """
📖 Description:
  Show system status.

⚙️  Usage:
  /system show

📝 Notes:
  - Manager, Worker and system modes are shown.
"""
        elif action == "validate":
            return """
📖 Description:
  Validates settings.

⚙️  Usage:
  /system validate

📝 Notes:
  - .env file is validated.
  - Errors and warnings are shown.

💡 Related Commands:
  /system reload   → Reload settings
"""
        elif action == "reload":
            return """
📖 Description:
  Reloads settings from .env.

⚙️  Usage:
  /system reload

📝 Notes:
  - .env file is re-read.
  - Session-based overrides are cleared.
  - Manager and Worker use new settings.

💡 Related Commands:
  /system show     → Show system status
  /system validate  → Validate settings
"""
        elif action == "reset":
            return """
📖 Description:
  Resets settings to defaults.

⚙️  Usage:
  /system reset

📝 Notes:
  - Planned for future implementation.
  - Not yet available.
  - Use /system reload to refresh from .env instead.
"""
        else:
            return f"No documentation for system action: {action}"

    def _get_mode_doc(self, action: str) -> str:
        """Mode documentation."""
        if action == "verbose":
            return """
📖 Description:
  Verbose output mode.

⚙️  Usage:
  /mode verbose

📝 Notes:
  - Shows every step of the worker.
  - Useful for debugging.
"""
        elif action == "quiet":
            return """
📖 Description:
  Quiet output mode.

⚙️  Usage:
  /mode quiet

📝 Notes:
  - Shows only the result.
  - Background processing.
"""
        elif action.startswith("confirm on"):
            return """
📖 Description:
  Confirmation mode on.

⚙️  Usage:
  /mode confirm on

📝 Notes:
  - Asks before running worker.
  - Useful for safety.
"""
        elif action.startswith("confirm off"):
            return """
📖 Description:
  Confirmation mode off.

⚙️  Usage:
  /mode confirm off

📝 Notes:
  - Worker runs automatically.
  - Useful for speed.
"""
        else:
            return f"No documentation for mode action: {action}"

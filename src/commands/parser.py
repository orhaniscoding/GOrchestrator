"""
Command Parser - Command parser and validator.

Parses user input and returns a Command object.
"""

from dataclasses import dataclass


@dataclass
class Command:
    """Parsed command object."""
    source: str           # manager, worker, session, system, mode
    action: str           # show, list, add, remove, set, etc.
    args: list[str]       # Command arguments
    options: dict[str, str]  # --global, --force, etc.


class CommandParser:
    """Command parser and validator."""

    # Command sources
    SOURCES = ["manager", "worker", "session", "system", "mode", "submanager", "team", "help"]

    # Options
    OPTIONS = ["--global", "--local", "--force", "--help"]

    # Command aliases: short -> full (consolidated from engine.py)
    ALIASES = {
        "/s": "/save",
        "/l": "/list",
        "/h": "/help",
        "/ct": "/clearterminal",
        "/w": "/worker",
        "/sm": "/submanager",
    }

    # Define commands and actions
    COMMAND_TREE = {
        "manager": [
            "show", "set profile", "set model", "set api", "set prompt",
            "llm", "rules", "temp", "tokens", "model", "api", "prompt",
            "profile", "list",
        ],
        "worker": ["list", "add", "remove", "show", "set"],
        "session": ["list", "show", "save", "new", "load"],
        "system": ["show", "validate", "reload"],
        "mode": ["verbose", "quiet", "confirm on", "confirm off"],
        "submanager": [
            "list", "add", "remove", "set", "show", "model", "profile",
            "api", "description", "llm",
        ],
        "team": [
            "list", "add", "remove", "activate", "deactivate", "show",
            "addmember", "removemember", "manager",
        ],
        "help": [],
    }

    def __init__(self):
        """Initialize the parser."""
        pass

    def parse(self, input: str) -> Command | None:
        """
        Parses input and returns a Command object.

        Args:
            input: User input (e.g.: "/manager set model gpt-4o --global")

        Returns:
            Command object or None (invalid command)
        """
        # Trim and split
        input = input.strip()
        if not input:
            return None

        # Slash check
        if not input.startswith("/"):
            return None

        # Resolve aliases before parsing
        first_token = input.split()[0]
        if first_token in self.ALIASES:
            input = self.ALIASES[first_token] + input[len(first_token):]

        # Remove slash
        input = input[1:]

        # Split
        parts = input.split()
        if not parts:
            return None

        # Parse options (trailing --global etc.)
        args = []
        options = {}
        i = len(parts) - 1
        while i >= 0:
            if parts[i].startswith("--"):
                options[parts[i]] = ""
                i -= 1
            else:
                break

        # Args (excluding options)
        args = parts[:i + 1]

        if not args:
            return None

        # Parse source and action
        source = args[0].lower()

        # Source validation
        if source not in self.SOURCES:
            return None

        # Action (optional)
        action = "show"
        action_args = []

        if len(args) > 1:
            # Try to match known compound actions like "set profile", "set model"
            valid_actions = self.COMMAND_TREE.get(source, [])

            # Try 2-word action match first (e.g., "set profile")
            if len(args) > 2:
                two_word = f"{args[1].lower()} {args[2].lower()}"
                if two_word in valid_actions:
                    action = two_word
                    action_args = args[3:]  # remaining tokens are arguments
                else:
                    action = args[1].lower()
                    action_args = args[2:]
            else:
                action = args[1].lower()
                action_args = args[2:]

        return Command(
            source=source,
            action=action,
            args=action_args,
            options=options
        )

    def validate(self, cmd: Command) -> bool:
        """
        Validates the command.

        Args:
            cmd: Command object

        Returns:
            True if valid, False if invalid
        """
        # Source validation
        if cmd.source not in self.SOURCES:
            return False

        # Action validation
        valid_actions = self.COMMAND_TREE.get(cmd.source, [])

        # Exact match check (e.g.: "show")
        if cmd.action in valid_actions:
            return True

        # Partial match check (e.g.: "set profile")
        for valid_action in valid_actions:
            if cmd.action.startswith(valid_action):
                return True

        return False

    def get_suggestions(self, partial_cmd: str) -> list[str]:
        """
        Returns suggestions for partial commands.

        Args:
            partial_cmd: Partial command (e.g.: "/manager set")

        Returns:
            List of suggestions
        """
        if not partial_cmd.startswith("/"):
            return []

        # Remove slash
        cmd = partial_cmd[1:].lower()
        parts = cmd.split()

        if not parts:
            # Suggest all sources
            return [f"/{source}" for source in self.SOURCES]

        source = parts[0]

        if source not in self.SOURCES:
            # Source suggestions
            return [f"/{s}" for s in self.SOURCES if s.startswith(source)]

        # Action suggestions for the source
        valid_actions = self.COMMAND_TREE.get(source, [])

        if len(parts) == 1:
            # Suggest all actions
            return [f"/{source} {action}" for action in valid_actions]

        # Partial action suggestions
        partial_action = " ".join(parts[1:])
        suggestions = []
        for action in valid_actions:
            if action.startswith(partial_action) or partial_action.startswith(action):
                suggestions.append(f"/{source} {action}")

        return suggestions

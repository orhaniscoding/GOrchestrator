"""
Tab Completion - Auto-completion system.

Hierarchical completion with context-aware suggestions.
Automatically built from CommandParser.COMMAND_TREE (single source of truth).
"""

from .parser import CommandParser


# Legacy flat commands that don't go through CommandParser
_LEGACY_FLAT_COMMANDS: dict[str, list[str] | None] = {
    "/help": None,
    "/save": None,
    "/load": None,
    "/list": None,
    "/new": None,
    "/clear": None,
    "/clearterminal": None,
    "/verbose": None,
    "/quiet": None,
    "/history": None,
    "/model": ["manager", "worker"],
    "/config": ["show", "reload", "validate", "set"],
    "/confirm": ["on", "off"],
    "/undo": None,
    "/checkpoints": None,
    "/exit": None,
    "/q": None,
    # Aliases
    "/s": None,
    "/l": None,
    "/h": None,
    "/ct": None,
    "/w": None,
    "/sm": None,
}


def _build_tree_from_command_tree() -> dict[str, list[str] | None]:
    """Build completer tree from CommandParser.COMMAND_TREE + legacy commands."""
    tree: dict[str, list[str] | None] = {}

    # Add structured commands from COMMAND_TREE
    for source, actions in CommandParser.COMMAND_TREE.items():
        key = f"/{source}"
        tree[key] = list(actions) if actions else None

    # Add legacy flat commands (won't overwrite structured ones)
    for cmd, subs in _LEGACY_FLAT_COMMANDS.items():
        if cmd not in tree:
            tree[cmd] = subs

    return tree


class TabCompleter:
    """Tab completion system."""

    def __init__(self):
        """Initialize the completer."""
        self.completer_tree = _build_tree_from_command_tree()

    def get_completions(self, text: str, state: int) -> str | None:
        """
        Returns tab completion values.

        Args:
            text: User input
            state: State (for prompt_toolkit)

        Returns:
            Completion list or None
        """
        # Parse partial command
        if not text.startswith("/"):
            return None

        # Hierarchical completion
        parts = text.split()
        if not parts:
            return None

        # Main command (e.g.: /manager, /worker)
        if len(parts) == 1:
            # Suggest all sources
            return self._get_root_completions(text, state)

        # Sub-command (e.g.: /manager set model)
        return self._get_nested_completions(text, state)

    def _get_root_completions(self, text: str, state: int) -> str | None:
        """Completions for main commands."""
        completions = []
        for cmd in self.completer_tree.keys():
            if cmd.startswith(text):
                completions.append(cmd)

        if state < len(completions):
            return completions[state]
        return None

    def _get_nested_completions(self, text: str, state: int) -> str | None:
        """Completions for nested commands."""
        parts = text.split()
        if len(parts) < 2:
            return None

        root_cmd = parts[0]

        if root_cmd not in self.completer_tree:
            return None

        sub_cmds = self.completer_tree[root_cmd]
        if not sub_cmds:
            return None

        # Partial text (last argument)
        partial = parts[-1] if len(parts) > 2 else ""

        completions = []
        for sub_cmd in sub_cmds:
            if not partial or sub_cmd.startswith(partial):
                # Suggest full command
                full_cmd = f"{root_cmd} {sub_cmd}"
                if full_cmd.startswith(text):
                    completions.append(full_cmd)

        if state < len(completions):
            return completions[state]
        return None

    def get_completer_tree(self) -> dict:
        """
        Returns the completer tree.

        Returns:
            Nested completer dictionary (for prompt_toolkit)
        """
        return self.completer_tree

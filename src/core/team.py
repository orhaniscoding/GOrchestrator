"""
Team - Organizational grouping of Main Manager + Sub-Managers.

A Team defines a specific combination of a Main Manager profile
and a set of Sub-Managers. Only one team can be active at a time.
When activated, the team sets the Main Manager profile and
activates only the specified sub-managers.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from .json_registry import JsonRegistry

logger = logging.getLogger(__name__)


@dataclass
class TeamConfig:
    """Configuration for a named team."""
    name: str
    main_manager_profile: str      # manager_profiles/<name>.yaml
    sub_manager_names: list[str] = field(default_factory=list)  # SubManagerRegistry names
    description: str = ""
    active: bool = False           # Only 1 team can be active at a time


class TeamRegistry(JsonRegistry[TeamConfig]):
    """Manages named team configurations persisted in teams.json."""

    def _item_from_dict(self, data: dict) -> TeamConfig:
        return TeamConfig(**data)

    def _item_to_dict(self, item: TeamConfig) -> dict:
        return {
            "name": item.name,
            "main_manager_profile": item.main_manager_profile,
            "sub_manager_names": item.sub_manager_names,
            "description": item.description,
            "active": item.active,
        }

    def get_active(self) -> TeamConfig | None:
        """Get the active team (only one can be active)."""
        for tc in self._items.values():
            if tc.active:
                return tc
        return None

    def add(
        self, name: str, main_manager_profile: str,
        sub_manager_names: list[str] | None = None,
        description: str = "",
    ) -> TeamConfig:
        if not name:
            raise ValueError("Team name cannot be empty")
        safe_name = self.sanitize_name(name)
        if not safe_name:
            raise ValueError("Team name cannot be empty after sanitization")
        if safe_name in self._items:
            raise ValueError(f"Team '{safe_name}' already exists")
        if safe_name != name:
            logger.info(f"Team name sanitized: '{name}' -> '{safe_name}'")
        tc = TeamConfig(
            name=safe_name,
            main_manager_profile=main_manager_profile,
            sub_manager_names=sub_manager_names or [],
            description=description,
            active=False,
        )
        self._items[safe_name] = tc
        self._save()
        return tc

    def activate(self, name: str) -> bool:
        """Activate a team (deactivates all others)."""
        if name not in self._items:
            return False
        for tc in self._items.values():
            tc.active = (tc.name == name)
        self._save()
        return True

    def deactivate(self, name: str | None = None) -> bool:
        """Deactivate a specific team, or all teams if name is None."""
        if name:
            if name not in self._items:
                return False
            self._items[name].active = False
        else:
            for tc in self._items.values():
                tc.active = False
        self._save()
        return True

    def update_main_manager(self, name: str, profile: str) -> bool:
        if name not in self._items:
            return False
        self._items[name].main_manager_profile = profile
        self._save()
        return True

    def add_sub_manager(self, team_name: str, sm_name: str) -> bool:
        if team_name not in self._items:
            return False
        tc = self._items[team_name]
        if sm_name not in tc.sub_manager_names:
            tc.sub_manager_names.append(sm_name)
            self._save()
        return True

    def remove_sub_manager(self, team_name: str, sm_name: str) -> bool:
        if team_name not in self._items:
            return False
        tc = self._items[team_name]
        if sm_name in tc.sub_manager_names:
            tc.sub_manager_names.remove(sm_name)
            self._save()
            return True
        return False

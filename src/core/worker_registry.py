"""
Worker Registry - Manages named worker profiles persisted in workers.json.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from .json_registry import JsonRegistry

logger = logging.getLogger(__name__)


@dataclass
class WorkerConfig:
    """Configuration for a named worker profile."""
    name: str
    model: str
    profile: str
    active: bool = False
    api_base: str | None = None
    api_key: str | None = None


class WorkerRegistry(JsonRegistry[WorkerConfig]):
    """Manages named worker profiles persisted in workers.json."""

    def _item_from_dict(self, data: dict) -> WorkerConfig:
        return WorkerConfig(**data)

    def _item_to_dict(self, item: WorkerConfig) -> dict:
        entry = {
            "name": item.name,
            "model": item.model,
            "profile": item.profile,
            "active": item.active,
        }
        if item.api_base:
            entry["api_base"] = item.api_base
        if item.api_key:
            entry["api_key"] = item.api_key
        return entry

    def ensure_default(self, model: str, profile: str):
        """Create a 'default' worker from .env values if registry is empty."""
        if not self._items:
            self._items["default"] = WorkerConfig(
                name="default", model=model, profile=profile, active=True,
            )
            self._save()

    def get_active(self) -> WorkerConfig | None:
        """Get the primary (first) active worker. For back-compat."""
        for wc in self._items.values():
            if wc.active:
                return wc
        return None

    def get_active_workers(self) -> list[WorkerConfig]:
        """Get all active workers."""
        return [wc for wc in self._items.values() if wc.active]

    def get_primary(self) -> WorkerConfig | None:
        """Get the primary worker (first active). Its settings go to .env."""
        active = self.get_active_workers()
        return active[0] if active else None

    def add(self, name: str, model: str, profile: str) -> WorkerConfig:
        safe_name = self.sanitize_name(name)
        if not safe_name:
            raise ValueError("Worker name cannot be empty after sanitization")
        if safe_name in self._items:
            raise ValueError(f"Worker '{safe_name}' already exists")
        if safe_name != name:
            logger.info(f"Worker name sanitized: '{name}' -> '{safe_name}'")
        wc = WorkerConfig(name=safe_name, model=model, profile=profile, active=False)
        self._items[safe_name] = wc
        self._save()
        return wc

    def remove(self, name: str) -> bool:
        if name not in self._items:
            return False
        del self._items[name]
        # If no active workers remain, activate the first one
        if self._items and not self.get_active_workers():
            first = next(iter(self._items.values()))
            first.active = True
        self._save()
        return True

    def set_active(self, name: str) -> bool:
        if name not in self._items:
            return False
        self._items[name].active = True
        self._save()
        return True

    def set_inactive(self, name: str) -> bool:
        if name not in self._items:
            return False
        self._items[name].active = False
        self._save()
        return True

    def update_model(self, name: str, model: str) -> bool:
        if name not in self._items:
            return False
        self._items[name].model = model
        self._save()
        return True

    def update_profile(self, name: str, profile: str) -> bool:
        if name not in self._items:
            return False
        self._items[name].profile = profile
        self._save()
        return True

    def update_api(self, name: str, api_base: str, api_key: str | None = None) -> bool:
        if name not in self._items:
            return False
        self._items[name].api_base = api_base
        if api_key:
            self._items[name].api_key = api_key
        self._save()
        return True

    def set_primary(self, name: str) -> bool:
        """Move worker to front of registry (primary = first active)."""
        if name not in self._items or not self._items[name].active:
            return False
        wc = self._items.pop(name)
        # Rebuild with this worker first
        new_workers = {name: wc}
        new_workers.update(self._items)
        self._items = new_workers
        self._save()
        return True

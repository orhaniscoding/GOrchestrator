"""
JSON Registry - Generic base class for dict-keyed JSON registries.

Provides common _load/_save/list_all/get/remove patterns shared by
WorkerRegistry, SubManagerRegistry, and TeamRegistry.

Note: LLMPool is NOT based on this class because it uses a JSON list
(not dict) root and has a dual-mode constructor (file-backed vs in-memory).
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar

from .config import SANITIZE_RE

logger = logging.getLogger(__name__)

T = TypeVar("T")


class JsonRegistry(ABC, Generic[T]):
    """
    Abstract base for dict-keyed JSON file registries.

    Subclasses must implement:
      - _item_from_dict(data) -> T
      - _item_to_dict(item) -> dict
    """

    def __init__(self, registry_file: Path):
        self._file = registry_file
        self._items: dict[str, T] = {}
        self._load()

    # ================================================================
    # Abstract methods
    # ================================================================

    @abstractmethod
    def _item_from_dict(self, data: dict) -> T:
        """Create an item instance from a deserialized dict."""

    @abstractmethod
    def _item_to_dict(self, item: T) -> dict:
        """Serialize an item to a dict for JSON persistence."""

    # ================================================================
    # Persistence
    # ================================================================

    def _load(self):
        """Load registry from disk."""
        if not self._file.exists():
            return
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._items = {
                name: self._item_from_dict(entry) for name, entry in data.items()
            }
        except json.JSONDecodeError as e:
            logger.warning(f"Corrupt registry file {self._file.name}: {e}. Starting fresh.")
            self._items = {}
        except Exception as e:
            logger.warning(f"Failed to load registry {self._file.name}: {e}")
            self._items = {}

    def _save(self):
        """Persist registry to disk atomically (temp file + os.replace)."""
        self._file.parent.mkdir(parents=True, exist_ok=True)
        data = {name: self._item_to_dict(item) for name, item in self._items.items()}
        tmp_path = self._file.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(str(tmp_path), str(self._file))

    # ================================================================
    # Common CRUD
    # ================================================================

    @staticmethod
    def sanitize_name(name: str) -> str:
        """Sanitize a name to only contain [a-zA-Z0-9_-]."""
        return SANITIZE_RE.sub("-", name)

    def list_all(self) -> list[T]:
        """Return all items."""
        return list(self._items.values())

    def get(self, name: str) -> T | None:
        """Get a single item by name."""
        return self._items.get(name)

    def remove(self, name: str) -> bool:
        """Remove an item by name. Subclasses may override for side effects."""
        if name not in self._items:
            return False
        del self._items[name]
        self._save()
        return True

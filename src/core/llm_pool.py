"""
LLM Pool - Parallel multi-LLM execution pool.

Manages a pool of LLM configurations that can be queried in parallel.
Each LLM receives the same messages (text-only, no tools) and the
"brain" LLM synthesizes the best answer from all responses.

Used by both Manager (file-backed persistence) and Sub-Manager (in-memory,
embedded in sub_managers.json).
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import call_litellm, mask_api_keys, SANITIZE_RE, get_executor

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """Configuration for a single LLM in the parallel pool."""
    name: str                        # Unique ID [a-zA-Z0-9_-]
    model: str                       # LLM model name
    api_base: str | None = None
    api_key: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


@dataclass
class LLMResponse:
    """Response from a single parallel LLM call."""
    name: str
    content: str
    model: str
    duration_seconds: float
    error: str | None = None


class LLMPool:
    """
    Manages a pool of LLM configurations for parallel execution.

    Two modes:
      - File-backed: registry_file is set, persists to JSON (Manager use).
      - In-memory: configs list provided, caller manages persistence (Sub-Manager use).
    """

    def __init__(
        self,
        registry_file: Path | None = None,
        configs: list[LLMConfig] | None = None,
    ):
        self._file = registry_file
        self._llms: dict[str, LLMConfig] = {}
        self._executor = get_executor()

        if configs:
            for cfg in configs:
                self._llms[cfg.name] = cfg
        elif registry_file:
            self._load()

    def shutdown(self):
        """Clean up references (shared executor is managed by config module)."""
        self._executor = None

    def __del__(self):
        """Ensure executor is shut down on garbage collection."""
        self.shutdown()

    # ================================================================
    # Persistence
    # ================================================================

    def _load(self):
        """Load LLM pool from disk (file-backed mode)."""
        if not self._file or not self._file.exists():
            return
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._llms = {}
            for entry in data:
                cfg = LLMConfig(
                    name=entry["name"],
                    model=entry["model"],
                    api_base=entry.get("api_base"),
                    api_key=entry.get("api_key"),
                    temperature=entry.get("temperature"),
                    max_tokens=entry.get("max_tokens"),
                )
                self._llms[cfg.name] = cfg
        except Exception as e:
            logger.warning(f"Failed to load LLM pool: {e}")
            self._llms = {}

    def _save(self):
        """Persist LLM pool to disk (file-backed mode)."""
        if not self._file:
            return
        self._file.parent.mkdir(parents=True, exist_ok=True)
        data = self.to_dict_list()
        with open(self._file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ================================================================
    # CRUD
    # ================================================================

    @staticmethod
    def sanitize_name(name: str) -> str:
        """Sanitize LLM name to only contain [a-zA-Z0-9_-]."""
        return SANITIZE_RE.sub("-", name)

    def list_all(self) -> list[LLMConfig]:
        """Return all LLM configs."""
        return list(self._llms.values())

    def get(self, name: str) -> LLMConfig | None:
        """Get a single LLM config by name."""
        return self._llms.get(name)

    def add(
        self,
        name: str,
        model: str,
        api_base: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMConfig:
        """Add an LLM to the pool."""
        safe_name = self.sanitize_name(name)
        if not safe_name:
            raise ValueError("LLM name cannot be empty after sanitization")
        if safe_name in self._llms:
            raise ValueError(f"LLM '{safe_name}' already exists in pool")
        if safe_name != name:
            logger.info(f"LLM name sanitized: '{name}' -> '{safe_name}'")
        cfg = LLMConfig(
            name=safe_name,
            model=model,
            api_base=api_base,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self._llms[safe_name] = cfg
        self._save()
        return cfg

    def remove(self, name: str) -> bool:
        """Remove an LLM from the pool."""
        if name not in self._llms:
            return False
        del self._llms[name]
        self._save()
        return True

    _UPDATABLE_FIELDS = {"model", "api_base", "api_key", "temperature", "max_tokens"}

    def update(self, name: str, **kwargs) -> bool:
        """Update an LLM's settings. Only allows safe fields to be modified."""
        cfg = self._llms.get(name)
        if not cfg:
            return False
        for key, value in kwargs.items():
            if key in self._UPDATABLE_FIELDS:
                setattr(cfg, key, value)
        self._save()
        return True

    def is_empty(self) -> bool:
        """Check if the pool has no LLMs."""
        return len(self._llms) == 0

    def count(self) -> int:
        """Return number of LLMs in the pool."""
        return len(self._llms)

    # ================================================================
    # Serialization (for Sub-Manager embedding)
    # ================================================================

    def to_dict_list(self) -> list[dict]:
        """Serialize pool to list of dicts (for JSON persistence)."""
        result = []
        for cfg in self._llms.values():
            entry = {"name": cfg.name, "model": cfg.model}
            if cfg.api_base:
                entry["api_base"] = cfg.api_base
            if cfg.api_key:
                entry["api_key"] = cfg.api_key
            if cfg.temperature is not None:
                entry["temperature"] = cfg.temperature
            if cfg.max_tokens is not None:
                entry["max_tokens"] = cfg.max_tokens
            result.append(entry)
        return result

    @classmethod
    def from_dict_list(cls, data: list[dict]) -> "LLMPool":
        """Create an in-memory pool from a list of dicts."""
        configs = []
        for entry in data:
            configs.append(LLMConfig(
                name=entry["name"],
                model=entry["model"],
                api_base=entry.get("api_base"),
                api_key=entry.get("api_key"),
                temperature=entry.get("temperature"),
                max_tokens=entry.get("max_tokens"),
            ))
        return cls(configs=configs)

    # ================================================================
    # Parallel Execution
    # ================================================================

    def _call_single_llm(self, cfg: LLMConfig, messages: list[dict]) -> LLMResponse:
        """Execute a single LLM call."""
        start_time = time.time()
        try:
            content, duration = call_litellm(
                model=cfg.model,
                messages=messages,
                api_base=cfg.api_base,
                api_key=cfg.api_key,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
            )
            return LLMResponse(
                name=cfg.name, content=content,
                model=cfg.model, duration_seconds=duration,
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Parallel LLM '{cfg.name}' call failed: {mask_api_keys(str(e))}")
            return LLMResponse(
                name=cfg.name, content="", model=cfg.model,
                duration_seconds=duration, error=mask_api_keys(str(e)),
            )

    def execute_parallel(
        self,
        messages: list[dict],
        on_response: Callable[[LLMResponse], None] | None = None,
    ) -> list[LLMResponse]:
        """
        Execute all LLMs in parallel with the same messages (text-only).

        Args:
            messages: Conversation messages in OpenAI format.
            on_response: Optional callback fired as each LLM responds (for live UI).

        Returns:
            List of LLMResponse objects.
        """
        if self.is_empty():
            return []

        configs = list(self._llms.values())

        # Single LLM: no thread overhead
        if len(configs) == 1:
            resp = self._call_single_llm(configs[0], messages)
            if on_response:
                on_response(resp)
            return [resp]

        # Parallel execution
        futures = {}
        for cfg in configs:
            future = self._executor.submit(self._call_single_llm, cfg, messages)
            futures[future] = cfg.name

        results = []
        for future in as_completed(futures):
            try:
                resp = future.result()
                results.append(resp)
                if on_response:
                    on_response(resp)
            except Exception as e:
                llm_name = futures[future]
                logger.error(f"Parallel LLM '{llm_name}' execution failed: {mask_api_keys(str(e))}")
                resp = LLMResponse(
                    name=llm_name, content="", model="unknown",
                    duration_seconds=0.0, error=mask_api_keys(str(e)),
                )
                results.append(resp)
                if on_response:
                    on_response(resp)

        return results

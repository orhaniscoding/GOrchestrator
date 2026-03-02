"""
Sub-Manager Agent - Expert advisor agents for the Mixture of Agents architecture.

Sub-Managers are LLM-powered advisors that provide specialized analysis.
They are consulted by the Main Manager via consult_* tools and return
text-only responses (no tool use). The Main Manager synthesizes their
analyses and decides on actions.

Key differences from Workers:
  - Sub-Managers do NOT execute code or commands
  - Sub-Managers return text analysis only
  - Sub-Managers are called via LiteLLM directly (no subprocess)
  - Multiple Sub-Managers can run in parallel via ThreadPoolExecutor
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from .config import call_litellm, mask_api_keys, get_executor
from .json_registry import JsonRegistry

logger = logging.getLogger(__name__)


@dataclass
class SubManagerConfig:
    """Configuration for a named sub-manager profile."""
    name: str           # Unique ID, sanitized [a-zA-Z0-9_-]
    profile: str        # YAML profile name (sub_manager_profiles/<profile>.yaml)
    model: str          # LLM model name
    description: str = ""
    active: bool = False
    api_base: str | None = None
    api_key: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    parallel_llms: list[dict] | None = None  # Embedded parallel LLM pool configs


@dataclass
class SubManagerResponse:
    """Response from a sub-manager consultation."""
    name: str
    content: str
    model: str
    duration_seconds: float
    error: str | None = None


class SubManagerRegistry(JsonRegistry[SubManagerConfig]):
    """Manages named sub-manager profiles persisted in sub_managers.json."""

    def _item_from_dict(self, data: dict) -> SubManagerConfig:
        return SubManagerConfig(**data)

    def _item_to_dict(self, item: SubManagerConfig) -> dict:
        entry = {
            "name": item.name,
            "profile": item.profile,
            "model": item.model,
            "description": item.description,
            "active": item.active,
        }
        if item.api_base:
            entry["api_base"] = item.api_base
        if item.api_key:
            entry["api_key"] = item.api_key
        if item.temperature is not None:
            entry["temperature"] = item.temperature
        if item.max_tokens is not None:
            entry["max_tokens"] = item.max_tokens
        if item.parallel_llms:
            entry["parallel_llms"] = item.parallel_llms
        return entry

    def get_active(self) -> list[SubManagerConfig]:
        """Get all active sub-managers."""
        return [sm for sm in self._items.values() if sm.active]

    def add(self, name: str, profile: str, model: str, description: str = "") -> SubManagerConfig:
        safe_name = self.sanitize_name(name)
        if not safe_name:
            raise ValueError("Sub-manager name cannot be empty after sanitization")
        if safe_name in self._items:
            raise ValueError(f"Sub-manager '{safe_name}' already exists")
        if safe_name != name:
            logger.info(f"Sub-manager name sanitized: '{name}' -> '{safe_name}'")
        sm = SubManagerConfig(
            name=safe_name, profile=profile, model=model,
            description=description, active=False,
        )
        self._items[safe_name] = sm
        self._save()
        return sm

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

    def update_description(self, name: str, description: str) -> bool:
        if name not in self._items:
            return False
        self._items[name].description = description
        self._save()
        return True

    def set_all_inactive(self):
        """Deactivate all sub-managers."""
        for sm in self._items.values():
            sm.active = False
        self._save()

    def activate_only(self, names: list[str]):
        """Activate only the specified sub-managers, deactivate all others."""
        for sm in self._items.values():
            sm.active = sm.name in names
        self._save()

    # ================================================================
    # Parallel LLM CRUD (embedded in sub_managers.json)
    # ================================================================

    def add_parallel_llm(
        self, sm_name: str, llm_name: str, model: str,
        api_base: str | None = None, api_key: str | None = None,
    ) -> bool:
        """Add a parallel LLM to a sub-manager's pool."""
        sm = self._items.get(sm_name)
        if not sm:
            return False
        if sm.parallel_llms is None:
            sm.parallel_llms = []
        # Check for duplicate
        for llm in sm.parallel_llms:
            if llm.get("name") == llm_name:
                return False
        entry: dict = {"name": llm_name, "model": model}
        if api_base:
            entry["api_base"] = api_base
        if api_key:
            entry["api_key"] = api_key
        sm.parallel_llms.append(entry)
        self._save()
        return True

    def remove_parallel_llm(self, sm_name: str, llm_name: str) -> bool:
        """Remove a parallel LLM from a sub-manager's pool."""
        sm = self._items.get(sm_name)
        if not sm or not sm.parallel_llms:
            return False
        original_len = len(sm.parallel_llms)
        sm.parallel_llms = [llm for llm in sm.parallel_llms if llm.get("name") != llm_name]
        if len(sm.parallel_llms) == original_len:
            return False
        if not sm.parallel_llms:
            sm.parallel_llms = None
        self._save()
        return True

    def list_parallel_llms(self, sm_name: str) -> list[dict] | None:
        """List parallel LLMs for a sub-manager."""
        sm = self._items.get(sm_name)
        if not sm:
            return None
        return sm.parallel_llms or []


class SubManagerAgent:
    """
    Handles LLM calls to sub-manager advisors.
    Sub-managers provide text-only analysis (no tools).
    """

    def __init__(self):
        self._executor = get_executor()

    def shutdown(self):
        """Clean up references (shared executor is managed by config module)."""
        self._executor = None
        if hasattr(self, '_executor') and self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None

    def __del__(self):
        """Ensure executor is shut down on garbage collection."""
        self.shutdown()

    def consult(
        self,
        config: SubManagerConfig,
        user_message: str,
        system_prompt: str,
        conversation_context: str = "",
    ) -> SubManagerResponse:
        """
        Consult a single sub-manager for analysis.

        Args:
            config: Sub-manager configuration.
            user_message: The user's original message/query.
            system_prompt: The sub-manager's system prompt from profile YAML.
            conversation_context: Optional recent conversation context.

        Returns:
            SubManagerResponse with the analysis result.
        """
        # Route to pool-based consultation if parallel LLMs are configured
        if config.parallel_llms:
            return self._consult_with_pool(
                config, user_message, system_prompt, conversation_context,
            )

        messages = [{"role": "system", "content": system_prompt}]
        if conversation_context:
            messages.append({
                "role": "user",
                "content": f"Recent conversation context:\n{conversation_context}\n\n---\nCurrent query: {user_message}",
            })
        else:
            messages.append({"role": "user", "content": user_message})

        start_time = time.time()
        try:
            content, duration = call_litellm(
                model=config.model,
                messages=messages,
                api_base=config.api_base,
                api_key=config.api_key,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            )
            return SubManagerResponse(
                name=config.name, content=content,
                model=config.model, duration_seconds=duration,
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Sub-manager '{config.name}' consultation failed: {mask_api_keys(str(e))}")
            return SubManagerResponse(
                name=config.name, content="", model=config.model,
                duration_seconds=duration, error=mask_api_keys(str(e)),
            )

    def consult_parallel(
        self,
        configs: list[SubManagerConfig],
        user_message: str,
        profiles: dict[str, dict],
        conversation_context: str = "",
    ) -> list[SubManagerResponse]:
        """
        Consult multiple sub-managers in parallel.

        Args:
            configs: List of sub-manager configurations.
            user_message: The user's original message/query.
            profiles: Dict mapping profile name -> loaded profile data (with system_prompt).
            conversation_context: Optional recent conversation context.

        Returns:
            List of SubManagerResponse objects.
        """
        if not configs:
            return []

        if len(configs) == 1:
            # Single call -- no thread overhead
            cfg = configs[0]
            profile_data = profiles.get(cfg.profile, {})
            system_prompt = profile_data.get("system_prompt", f"You are an expert advisor named {cfg.name}.")
            return [self.consult(cfg, user_message, system_prompt, conversation_context)]

        # Parallel execution
        futures = {}
        for cfg in configs:
            profile_data = profiles.get(cfg.profile, {})
            system_prompt = profile_data.get("system_prompt", f"You are an expert advisor named {cfg.name}.")
            future = self._executor.submit(
                self.consult, cfg, user_message, system_prompt, conversation_context,
            )
            futures[future] = cfg.name

        results = []
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                sm_name = futures[future]
                logger.error(f"Parallel sub-manager '{sm_name}' failed: {e}")
                results.append(SubManagerResponse(
                    name=sm_name, content="", model="unknown",
                    duration_seconds=0.0, error=str(e),
                ))

        return results

    def _consult_with_pool(
        self,
        config: SubManagerConfig,
        user_message: str,
        system_prompt: str,
        conversation_context: str = "",
    ) -> SubManagerResponse:
        """
        Consult a sub-manager using its parallel LLM pool.
        Parallel LLMs analyze first, then the brain LLM (sub-manager's own model) synthesizes.

        Args:
            config: Sub-manager configuration (with parallel_llms).
            user_message: The user's original message/query.
            system_prompt: The sub-manager's system prompt.
            conversation_context: Optional recent conversation context.

        Returns:
            SubManagerResponse with the synthesized analysis.
        """
        from .llm_pool import LLMPool

        pool = LLMPool.from_dict_list(config.parallel_llms)

        # Build messages for parallel LLMs
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_context:
            messages.append({
                "role": "user",
                "content": f"Recent conversation context:\n{conversation_context}\n\n---\nCurrent query: {user_message}",
            })
        else:
            messages.append({"role": "user", "content": user_message})

        # Fan-out to parallel LLMs
        parallel_responses = pool.execute_parallel(messages=messages)
        valid = [r for r in parallel_responses if not r.error]

        if not valid:
            # All parallel LLMs failed, fall back to normal consult
            return self.consult(config, user_message, system_prompt, conversation_context)

        # Build synthesis prompt for brain LLM
        synthesis_parts = [
            "Multiple LLM models have analyzed the query in parallel. "
            "Synthesize the best answer from their analyses:\n\n---\n"
        ]
        for resp in parallel_responses:
            if resp.error:
                synthesis_parts.append(
                    f"### LLM: {resp.name} (model: {resp.model}) — ERROR\n"
                    f"Error: {resp.error}\n\n"
                )
            else:
                synthesis_parts.append(
                    f"### LLM: {resp.name} (model: {resp.model}, {resp.duration_seconds:.1f}s)\n"
                    f"{resp.content}\n\n"
                )
        synthesis_parts.append("---\n")
        synthesis_parts.append(
            "Synthesize the above into a single, coherent, authoritative analysis."
        )
        synthesis_message = "\n".join(synthesis_parts)

        # Brain LLM call (sub-manager's own model) with synthesis
        synthesis_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": synthesis_message},
        ]

        start_time = time.time()
        try:
            content, duration = call_litellm(
                model=config.model,
                messages=synthesis_messages,
                api_base=config.api_base,
                api_key=config.api_key,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            )
            return SubManagerResponse(
                name=config.name, content=content,
                model=config.model, duration_seconds=duration,
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Sub-manager '{config.name}' synthesis failed: {mask_api_keys(str(e))}")
            return SubManagerResponse(
                name=config.name, content="", model=config.model,
                duration_seconds=duration, error=mask_api_keys(str(e)),
            )

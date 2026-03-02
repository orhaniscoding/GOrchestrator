# Changelog

All notable changes to GOrchestrator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.1] - 2026-02-23

### Security

- **Removed hardcoded API key** from `manager_profiles/default.yaml`
- **API key masking** in all error logs, session history exports, and sub-manager/LLM pool errors via `mask_api_keys()`
- **Path traversal prevention** via `validate_profile_name()` for Manager and Sub-Manager profile loading
- **Environment allowlist** for Worker subprocess (`_ENV_ALLOWLIST`) to prevent credential leakage
- **`LLMPool.update()` field allowlist** (`_UPDATABLE_FIELDS`) to prevent arbitrary attribute injection via `setattr`
- Created `SECURITY.md` with vulnerability disclosure policy

### Fixed

- **`write_env_value()` corruption bug**: Lines with `#` in values (e.g., URLs) were silently truncated; now uses regex-based parsing
- **`temperature=0.0` silently dropped**: `if config.get("temperature"):` treated `0.0` as falsy; changed to `is not None` check
- **`get_settings()` `lru_cache` issue**: Replaced with explicit singleton pattern to support `reload_settings()` properly
- **11 failing engine tests**: `CommandHandler._handle_worker()` was not forwarding `cmd.args` to sub-handlers
- **`.env.example` contradiction**: Fixed misleading comment about runtime override behavior
- **README.md**: Fixed placeholder repository URL, broken CONTRIBUTING.md link, updated test count

### Added

- **`JsonRegistry[T]` base class** (`src/core/json_registry.py`): Generic abstract base for dict-keyed JSON registries, reducing code duplication across WorkerRegistry, SubManagerRegistry, and TeamRegistry
- **`CheckpointManager`** (`src/core/checkpoint_manager.py`): Extracted git checkpoint system from engine.py into dedicated class
- **`call_litellm()` shared utility** in `config.py`: Unified LLM call wrapper for sub-managers and LLM pools
- **`test_team.py`**: 18 tests covering TeamRegistry CRUD, activate/deactivate, sub-manager operations, persistence
- **`test_worker.py`**: 25 tests covering AgentWorker command building, env allowlist, noise filtering, process termination, run_task error handling
- **Dependency version pins** in `pyproject.toml` for pyyaml, requests, jinja2, tenacity, typer, platformdirs, openai

### Changed

- **WorkerRegistry** extracted from `engine.py` to `src/core/worker_registry.py`
- **WorkerRegistry, SubManagerRegistry, TeamRegistry** refactored to inherit from `JsonRegistry[T]`
- **Sub-Manager and LLM Pool** refactored to use `call_litellm()` instead of direct `litellm.completion()`
- **ThreadPoolExecutor cleanup**: Added `shutdown()` and `__del__` methods to Manager, SubManagerAgent, and LLMPool
- **Commands system**: All Turkish text translated to English in `src/commands/`
- **Entry point consolidated**: Single `gorchestrator = "src.core:main"` in `pyproject.toml`
- Removed `sys.path.insert` hack from `main.py`
- Test count: 194 → 237

### Removed

- Duplicate `mini` and `gocore` entry points from `pyproject.toml`
- Inline checkpoint methods from `engine.py` (moved to `CheckpointManager`)
- Copy-paste `_load`/`_save` boilerplate from registries (replaced by `JsonRegistry` base)

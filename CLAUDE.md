# CLAUDE.md - GOrchestrator Project Guide

## Project Overview

GOrchestrator is an Intelligent AI Agent Manager that acts as a Software Architect. A Manager agent understands user requirements, consults Sub-Manager advisors, plans solutions, and delegates coding tasks to Worker agents in parallel.

## Quick Commands

```bash
# Run the application
uv run python main.py

# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_config.py -v

# Run specific test class
uv run pytest tests/test_manager.py::TestLiteLLMRouting -v

# Type check (if needed)
uv run python -m py_compile src/core/config.py
```

## Project Structure

```
GOrchestrator/
├── main.py                     # CLI entry point
├── pyproject.toml              # Dependencies (uv/pip)
├── .env / .env.example         # Configuration
├── src/
│   ├── core/                   # Core business logic
│   │   ├── config.py           # Settings (pydantic-settings), detect_provider(), SANITIZE_RE
│   │   ├── json_registry.py    # Generic JsonRegistry[T] base class
│   │   ├── manager.py          # Manager Agent (LiteLLM unified routing)
│   │   ├── worker.py           # Worker subprocess wrapper
│   │   ├── worker_registry.py  # WorkerRegistry (extends JsonRegistry)
│   │   ├── engine.py           # Session engine, slash commands
│   │   ├── checkpoint_manager.py # Git-based checkpoint/undo system
│   │   ├── sub_manager.py      # Sub-Manager advisory agents (Mixture of Agents)
│   │   ├── llm_pool.py         # Parallel multi-LLM execution pool
│   │   └── team.py             # Team management (Manager + Sub-Manager combos)
│   ├── commands/               # Command system
│   │   ├── parser.py           # CommandParser, SOURCES, COMMAND_TREE
│   │   ├── handlers.py         # CommandHandler (routes to engine methods)
│   │   ├── completer.py        # Tab completion (prompt_toolkit)
│   │   └── help.py             # Help text generation
│   ├── ui/
│   │   └── console.py          # Rich terminal UI, dashboard
│   ├── utils/
│   │   └── parser.py           # Worker JSON log parser
│   └── worker_core/            # Integrated Mini-SWE-GOCore agent
├── tests/                      # 282 unit tests
│   ├── test_config.py          # Settings + provider detection
│   ├── test_engine.py          # Session engine + worker management
│   ├── test_manager.py         # Manager agent + LiteLLM routing
│   ├── test_llm_pool.py        # LLM Pool CRUD + parallel execution
│   ├── test_sub_manager.py     # Sub-Manager registry
│   ├── test_team.py            # Team registry CRUD + persistence
│   ├── test_worker.py          # Worker command/env/noise/process tests
│   ├── test_commands_parser.py # Command parser
│   └── test_parser.py          # Log parser
├── docs/                       # Documentation
└── .gorchestrator/             # Runtime data (gitignored)
    ├── sessions/               # Per-session directories
    ├── workers.json            # Worker registry
    ├── sub_managers.json       # Sub-Manager registry
    ├── teams.json              # Team registry
    └── manager_llm_pool.json   # Manager LLM Pool
```

## Key Architecture Decisions

- **LiteLLM unified routing**: Single `_call_llm()` method with `custom_llm_provider` for all LLM providers (Anthropic, OpenAI, Google, etc.)
- **Provider detection**: `detect_provider()` in `config.py` maps model names to providers automatically
- **SANITIZE_RE centralization**: All name sanitization uses `SANITIZE_RE` from `config.py` (not local copies)
- **pydantic-settings**: Type-safe configuration with `.env` file support and `write_env_value()` for runtime persistence
- **ThreadPoolExecutor**: Parallel execution for workers, sub-managers, and LLM pools

## Development Rules

- **Language**: Code in English (variable names, docstrings, comments)
- **Style**: PEP 8, type hints on all public functions
- **Imports**: Use relative imports within `src/` package
- **Testing**: All new features must have corresponding tests in `tests/`
- **Name sanitization**: Always use `SANITIZE_RE` from `config.py`, never create local regex patterns
- **API keys**: Never log or display full API keys. Use `f"****...{key[-4:]}"` format for display
- **Config persistence**: Runtime changes should call `write_env_value()` to persist to `.env`

## Important Patterns

### Provider Detection Flow
```
model_name → detect_provider() → "anthropic"/"openai"/"google"
model_name → strip_provider_prefix() → clean model name
Both passed to litellm.completion(custom_llm_provider=provider)
```

### Command Flow
```
User input → CommandParser.parse() → Command(source, action, args, options)
           → CommandHandler.handle() → engine._handle_*_command()
```

### Worker Delegation Flow
```
Manager._call_llm() → tool_calls: delegate_to_<name>
→ _resolve_worker() → WorkerConfig
→ ThreadPoolExecutor → worker.run_task() → subprocess
→ TaskResult → tool response → Manager._call_llm() (final summary)
```

## Known Issues

- 16 engine tests fail due to test fixture infrastructure issues (pre-existing, not caused by recent changes)
- Worker Core (Mini-SWE-GOCore) is an integrated submodule with its own test suite

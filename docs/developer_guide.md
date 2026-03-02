# Developer Guide

This guide is for developers who want to understand, extend, or contribute to GOrchestrator.

## Table of Contents

- [Project Structure](#project-structure)
- [Development Setup](#development-setup)
- [Core Concepts](#core-concepts)
- [LiteLLM-Based Routing](#litellm-based-routing)
- [Sub-Manager System](#sub-manager-system)
- [LLM Pool](#llm-pool)
- [Team Management](#team-management)
- [Dynamic Tool System](#dynamic-tool-system)
- [Adding New Tools](#adding-new-tools)
- [Customizing the UI](#customizing-the-ui)
- [Adding Slash Commands](#adding-slash-commands)
- [Testing](#testing)
- [Code Style](#code-style)
- [Debugging Tips](#debugging-tips)

---

## Project Structure

```
GOrchestrator/
├── main.py                     # CLI entry point
├── pyproject.toml              # Dependencies & project config
├── .env.example                # Configuration template
├── README.md                   # Project overview
├── CONTRIBUTING.md             # Contribution guidelines
│
├── src/                        # Source code
│   ├── __init__.py
│   │
│   ├── core/                   # Core business logic
│   │   ├── __init__.py         # Public API exports
│   │   ├── config.py           # Settings, provider detection, env persistence, SANITIZE_RE
│   │   ├── manager.py          # Manager Agent (LiteLLM unified routing)
│   │   ├── worker.py           # Worker subprocess wrapper
│   │   ├── engine.py           # Session engine, WorkerRegistry, slash commands
│   │   ├── sub_manager.py      # Sub-Manager advisory agents (Mixture of Agents)
│   │   ├── llm_pool.py         # Parallel multi-LLM execution pool
│   │   └── team.py             # Team management (Manager + Sub-Manager combos)
│   │
│   ├── commands/               # Command system
│   │   ├── __init__.py
│   │   ├── parser.py           # Command parser and validator
│   │   ├── handlers.py         # Command handlers for all sources
│   │   ├── completer.py        # Tab completion system
│   │   └── help.py             # Help system
│   │
│   ├── ui/                     # User interface
│   │   ├── __init__.py
│   │   └── console.py          # Rich terminal UI, dashboard, autocomplete
│   │
│   ├── utils/                  # Utilities
│   │   ├── __init__.py
│   │   └── parser.py           # Worker JSON log parser
│   │
│   └── worker_core/            # Integrated worker engine (Mini-SWE-GOCore)
│       ├── __init__.py
│       ├── minisweagent/       # Agent code (models, agents, config, etc.)
│       └── .miniswe/           # Runtime configs and data
│
├── tests/                      # Unit tests (200+ tests)
│   ├── __init__.py
│   ├── test_config.py          # Settings + provider detection tests
│   ├── test_engine.py          # Session engine + worker management tests
│   ├── test_manager.py         # Manager agent + LiteLLM routing tests
│   ├── test_llm_pool.py        # LLM Pool CRUD, persistence, parallel execution
│   ├── test_sub_manager.py     # Sub-Manager registry tests
│   ├── test_commands_parser.py # Command parser tests
│   └── test_parser.py          # Log parser tests
│
├── docs/                       # Documentation
│   ├── architecture.md         # Technical architecture
│   ├── user_guide.md           # User guide
│   ├── setup_guide.md          # Installation walkthrough
│   └── developer_guide.md      # This file
│
└── .gorchestrator/             # Runtime data (gitignored)
    ├── sessions/               # Per-session directories
    ├── workers.json            # Worker registry
    └── gorchestrator.log       # Application log file
```

### Module Responsibilities

| Module | Purpose |
|--------|---------|
| `core/config.py` | Settings via pydantic-settings, `detect_provider()`, `strip_provider_prefix()`, `write_env_value()`, `get_agent_env()`, `SANITIZE_RE`, `sanitize_name()` |
| `core/manager.py` | LiteLLM unified routing (`custom_llm_provider`), dynamic tool system, parallel worker execution, sub-manager consultation |
| `core/worker.py` | Subprocess wrapper for integrated worker core with per-worker API override |
| `core/engine.py` | Session loop, `WorkerRegistry`, `WorkerConfig`, `SLASH_COMMAND_TREE`, slash command handlers, checkpoint system |
| `core/sub_manager.py` | `SubManagerRegistry`, `SubManagerConfig`, advisory agent consultation, per-sub-manager LLM pools |
| `core/llm_pool.py` | `LLMPool`, `LLMConfig`, `LLMResponse`, parallel multi-LLM execution via ThreadPoolExecutor |
| `core/team.py` | `TeamRegistry`, `TeamConfig`, saved Manager + Sub-Manager combinations |
| `commands/parser.py` | `CommandParser`, `Command`, SOURCES/COMMAND_TREE validation |
| `commands/handlers.py` | `CommandHandler`, routes parsed commands to engine methods |
| `commands/completer.py` | Tab completion for slash commands via prompt_toolkit |
| `commands/help.py` | Help text generation |
| `ui/console.py` | Rich terminal: dashboard, autocomplete (NestedCompleter), SafeFileHistory, worker output tagging |
| `utils/parser.py` | Parse Worker JSON log lines into structured entries |
| `worker_core/` | Integrated Mini-SWE-GOCore engine -- autonomous coding agent with LiteLLM |

---

## Development Setup

### 1. Clone and Install

```bash
git clone https://github.com/orhaniscoding/GOrchestrator.git
cd GOrchestrator

# Install all dependencies (includes worker core deps)
uv sync
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Run in Development

```bash
uv run python main.py
```

---

## Core Concepts

### 1. The Manager Agent

The Manager Agent (`src/core/manager.py`) is the heart of GOrchestrator. It uses LiteLLM for unified provider-aware routing.

```python
class ManagerAgent:
    def __init__(self, settings, worker_registry, on_worker_output, on_thinking):
        self.settings = settings
        self.worker = AgentWorker(settings)
        self.worker_registry = worker_registry
        self.messages = []
        self.on_worker_output = on_worker_output  # fn(line, worker_name)
        self.on_thinking = on_thinking
        self._add_system_message()

    def chat(self, user_message: str) -> ManagerResponse:
        # 1. Add user message to history
        # 2. Call LLM via _call_llm() (LiteLLM unified routing)
        # 3. Handle any tool calls (parallel if multiple)
        # 4. Return final response
```

### 2. Provider Detection

Provider is detected from the model name in `config.py`:

```python
def detect_provider(model_name: str) -> str:
    # "anthropic/claude-opus-4" → "anthropic" (explicit prefix)
    # "claude-sonnet-4-20250514"        → "anthropic" (keyword match)
    # "gpt-4o"                    → "openai" (keyword match)
    # "gemini-pro"                → "google" (keyword match)
    # "anything-else"             → "openai" (default)
```

### 3. Worker Registry

Workers are managed by `WorkerRegistry` in `worker_registry.py`, persisted to `.gorchestrator/workers.json`:

```python
@dataclass
class WorkerConfig:
    name: str
    model: str
    profile: str
    active: bool = False
    api_base: str | None = None
    api_key: str | None = None

class WorkerRegistry:
    def ensure_default(self, model, profile)  # Create default from .env
    def list_all(self) -> list[WorkerConfig]
    def get_active_workers(self) -> list[WorkerConfig]
    def get_primary(self) -> WorkerConfig | None
    def add(self, name, model, profile) -> WorkerConfig
    def remove(self, name) -> bool
    def update_api(self, name, api_base, api_key) -> bool
```

### 4. Session Persistence

Sessions use unique IDs with random names (e.g., `bold-phoenix-a1b2c3d4`) and are stored in per-session directories under `.gorchestrator/sessions/`.

---

## LiteLLM-Based Routing

Both Manager and Worker use **LiteLLM** with `custom_llm_provider` for unified provider-aware routing. This is the same library and same pattern in both layers.

### How It Works

The Manager's `_call_llm()` method uses a single LiteLLM call:

```python
def _call_llm(self, include_tools=True):
    config = self.settings.get_orchestrator_config()
    model_name = strip_provider_prefix(config["model"])
    provider = detect_provider(config["model"])

    kwargs = {
        "model": model_name,
        "messages": [msg.to_dict() for msg in self.messages],
        "max_tokens": 4096,
        "api_base": config["api_base"],
        "api_key": config["api_key"],
        "custom_llm_provider": provider,  # "anthropic", "openai", "google"
    }

    if include_tools:
        kwargs["tools"] = self._build_worker_tools()
        kwargs["tool_choice"] = "auto"

    # Extended thinking for *-thinking models
    if "thinking" in model_name.lower():
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": 10000}
        kwargs["max_tokens"] = 16000

    return litellm.completion(**kwargs)
```

LiteLLM handles automatically:
- Native API format per provider (Anthropic `/v1/messages` vs OpenAI `/v1/chat/completions`)
- URL suffix management (no manual `/v1` appending needed)
- Response normalization to OpenAI format
- Extended thinking parameter forwarding

### Adding a New Provider

To add support for a new provider (e.g., Cohere):

1. Add keywords to `config.py`:
   ```python
   _COHERE_KEYWORDS = ("command-r",)
   ```

2. Update `detect_provider()`:
   ```python
   if any(k in name for k in _COHERE_KEYWORDS):
       return "cohere"
   ```

3. Add tests in `test_config.py` and `test_manager.py`

That's it -- LiteLLM handles the rest. No new SDK, no new `_call_*` method needed.

---

## Sub-Manager System

### Architecture

Sub-Managers (`src/core/sub_manager.py`) are expert advisor AI agents managed by `SubManagerRegistry`. They provide specialized analysis (architecture, security, code review) that the Manager synthesizes before delegating tasks.

```python
class SubManagerRegistry:
    def __init__(self, registry_file: Path):
        self._registry: dict[str, SubManagerConfig] = {}

    def add(name, profile, model, description) -> SubManagerConfig
    def remove(name) -> bool
    def set_active(name) / set_inactive(name) -> bool
    def activate_only(names: list[str])
    def get_active() -> list[SubManagerConfig]
    def update_model(name, model) / update_profile(name, profile) -> bool
    def update_api(name, api_base, api_key) -> bool
    def add_parallel_llm(name, llm_name, model) -> bool
    def remove_parallel_llm(name, llm_name) -> bool
```

### Adding a New Sub-Manager Profile

1. Create a YAML file in `src/worker_core/.miniswe/configs/sub_managers/`:
   ```yaml
   # my_advisor.yaml
   system_prompt: "You are a specialized advisor for..."
   temperature: 0.7
   max_tokens: 4096
   ```

2. Use it: `/submanager add my-advisor my_advisor claude-sonnet-4-20250514`

### Name Sanitization

All sub-manager names are sanitized using `SANITIZE_RE` from `config.py`:
```python
from .config import SANITIZE_RE
name = SANITIZE_RE.sub("-", raw_name)  # "my.advisor!" → "my-advisor-"
```

---

## LLM Pool

### Architecture

The `LLMPool` class (`src/core/llm_pool.py`) manages parallel multi-LLM execution. It supports both file-backed persistence and in-memory mode.

```python
class LLMPool:
    def __init__(self, registry_file: Path | None = None):
        # None = in-memory mode (for sub-manager embedded pools)
        self._llms: dict[str, LLMConfig] = {}

    def add(name, model, api_base, api_key) -> LLMConfig
    def remove(name) -> bool
    def execute_parallel(messages, system_prompt, on_response) -> list[LLMResponse]
    def to_dict_list() -> list[dict]       # For embedding in sub-manager JSON
    def from_dict_list(data: list[dict])   # Restore from sub-manager JSON
```

### Parallel Execution

```python
def execute_parallel(self, messages, system_prompt=None, on_response=None):
    with ThreadPoolExecutor(max_workers=len(self._llms)) as executor:
        futures = {
            executor.submit(self._call_single, llm, messages, system_prompt): llm
            for llm in self._llms.values()
        }
        results = []
        for future in as_completed(futures):
            response = future.result()
            if on_response:
                on_response(response)  # Callback for streaming
            results.append(response)
    return results
```

### Usage Contexts

| Context | Storage | Description |
|---------|---------|-------------|
| Manager LLM Pool | `.gorchestrator/manager_llm_pool.json` | Manager queries multiple LLMs |
| Sub-Manager Pool | Embedded in `sub_managers.json` | Per-sub-manager parallel LLMs |

---

## Team Management

### Architecture

Teams (`src/core/team.py`) are saved combinations of a Manager profile and Sub-Manager names. `TeamRegistry` handles CRUD and activation.

```python
class TeamRegistry:
    def __init__(self, registry_file: Path):
        self._teams: dict[str, TeamConfig] = {}

    def add(name, manager_profile, sub_managers) -> TeamConfig
    def remove(name) -> bool
    def activate(name, sub_manager_registry) -> bool
    def deactivate(sub_manager_registry) -> None
    def add_member(team_name, sm_name) -> bool
    def remove_member(team_name, sm_name) -> bool
```

### Activation Flow

```
/team activate review-team
    │
    ├── 1. Set Manager profile to team.manager_profile
    ├── 2. Call sub_manager_registry.activate_only(team.sub_managers)
    │       ├── Deactivate all current sub-managers
    │       └── Activate only the ones in the team
    └── 3. Rebuild Manager system prompt with new profile + active advisors
```

---

## Dynamic Tool System

### How Tools Are Generated

Tools are dynamically generated from active workers:

```python
def _build_worker_tools(self) -> list[dict]:
    tools = []
    for wc in worker_registry.get_active_workers():
        safe_name = _sanitize_tool_name(wc.name)
        tools.append({
            "type": "function",
            "function": {
                "name": f"delegate_to_{safe_name}",
                "description": f"Delegate to Worker '{wc.name}' "
                               f"(model: {wc.model}, profile: {wc.profile})...",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_description": {"type": "string", ...},
                        "context": {"type": "string", ...}
                    },
                    "required": ["task_description"]
                }
            }
        })
    return tools
```

LiteLLM handles tool format conversion for each provider automatically.

### Tool Resolution

When the LLM calls a tool, `_resolve_worker()` maps the tool name back to a `WorkerConfig`:

```python
def _resolve_worker(self, tool_name: str) -> WorkerConfig | None:
    # "delegate_to_coder" → WorkerConfig(name="coder", ...)
    # "delegate_to_worker" → None (legacy, uses default settings)
```

### Parallel Execution

Multiple tool calls execute in parallel via `ThreadPoolExecutor`:

```python
with ThreadPoolExecutor(max_workers=len(tool_calls)) as executor:
    futures = {
        executor.submit(self._execute_single_tool_call, tc): tc
        for tc in tool_calls
    }
    for future in as_completed(futures):
        result, message = future.result()
```

---

## Adding Slash Commands

### Step 1: Register in SLASH_COMMAND_TREE

```python
SLASH_COMMAND_TREE: dict[str, list[str] | None] = {
    # ... existing commands ...
    "/export": None,  # No sub-commands
    "/stats": ["session", "workers"],  # With sub-commands
}
```

This automatically enables tab-completion via NestedCompleter.

### Step 2: Add Handler

```python
def _handle_slash_command(self, command: str) -> bool:
    # ... existing handlers ...
    elif cmd == "/export":
        self._handle_export_command(arg)
        return True
```

### Step 3: Add Alias (Optional)

```python
_COMMAND_ALIASES = {
    "/e": "/export",
}
```

---

## Testing

### Test Structure

| File | Tests | Coverage |
|------|-------|----------|
| `test_config.py` | Settings, provider detection, env persistence | `config.py` |
| `test_engine.py` | Session engine, worker management, slash commands | `engine.py` |
| `test_manager.py` | Manager agent, LiteLLM routing, tool system, command handlers | `manager.py`, `engine.py` |
| `test_llm_pool.py` | LLM Pool CRUD, persistence, serialization, parallel execution | `llm_pool.py` |
| `test_sub_manager.py` | Sub-Manager registry CRUD, persistence, parallel LLM management | `sub_manager.py` |
| `test_commands_parser.py` | Command parser, validation, suggestions | `commands/parser.py` |
| `test_parser.py` | Log line parsing | `utils/parser.py` |

### Key Test Patterns

**LiteLLM routing tests:**
```python
class TestLiteLLMRouting:
    @patch("src.core.manager.litellm")
    def test_call_llm_passes_custom_llm_provider(self, mock_litellm):
        # Verify custom_llm_provider is passed correctly
        call_kwargs = mock_litellm.completion.call_args
        assert call_kwargs.kwargs["custom_llm_provider"] == "anthropic"

    @patch("src.core.manager.litellm")
    def test_call_llm_thinking_model(self, mock_litellm):
        # Verify thinking params for *-thinking models
        assert call_kwargs.kwargs["thinking"] == {"type": "enabled", "budget_tokens": 10000}
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_config.py -v

# Run specific test class
uv run pytest tests/test_manager.py::TestLiteLLMRouting -v
```

---

## Debugging Tips

### Application Logs

GOrchestrator logs to `.gorchestrator/gorchestrator.log`:

```bash
# View recent logs (PowerShell)
Get-Content .gorchestrator\gorchestrator.log -Tail 50 -Wait

# View recent logs (Unix)
tail -f .gorchestrator/gorchestrator.log
```

### Debug LLM Calls

Enable LiteLLM verbose logging:
```python
import litellm
litellm.set_verbose = True
```

Or set environment variable:
```bash
LITELLM_LOG=DEBUG
```

### Config Validation

Use `/config validate` at runtime to check for common issues (missing paths, invalid keys, etc.).

---

<p align="center">
  <strong>Happy coding! We look forward to your contributions.</strong>
</p>

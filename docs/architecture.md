# Architecture

This document explains the technical architecture of GOrchestrator and how its components interact.

## Table of Contents

- [System Overview](#system-overview)
- [The Manager-Worker Pattern](#the-manager-worker-pattern)
- [Provider-Aware LLM Routing](#provider-aware-llm-routing)
- [Multi-Worker Architecture](#multi-worker-architecture)
- [Sub-Manager Advisory System](#sub-manager-advisory-system)
- [Parallel LLM Pool](#parallel-llm-pool)
- [Team Management](#team-management)
- [Component Details](#component-details)
- [Data Flow](#data-flow)
- [Session Management](#session-management)
- [Checkpoint System](#checkpoint-system)
- [Dynamic Tool System](#dynamic-tool-system)
- [Environment Variable Injection](#environment-variable-injection)

---

## System Overview

GOrchestrator implements a **Manager-MultiWorker** architecture where an intelligent LLM-powered Manager Agent orchestrates conversations with users and delegates coding tasks to one or more Worker Agents, with LiteLLM-based unified provider routing.

```
┌───────────────────────────────────────────────────────────────────────────┐
│                           SYSTEM ARCHITECTURE                             │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│    ┌─────────────┐                                                        │
│    │    USER     │                                                        │
│    │   (Human)   │                                                        │
│    └──────┬──────┘                                                        │
│           │ Natural Language / Slash Commands                              │
│           ▼                                                               │
│    ┌─────────────────────────────────────────────────────────────────┐    │
│    │                       GORCHESTRATOR                              │    │
│    │                                                                  │    │
│    │  ┌───────────┐  ┌───────────┐  ┌──────────────────────────┐    │    │
│    │  │ Console UI│  │  Session  │  │     Manager Agent         │    │    │
│    │  │ Dashboard │  │  Engine   │  │  LiteLLM Unified Routing  │    │    │
│    │  │ Autocmpl. │  │ Registry │  │  (custom_llm_provider)    │    │    │
│    │  └───────────┘  └───────────┘  └─────────┬────────────────┘    │    │
│    │                                           │                     │    │
│    │                          Dynamic Tools: delegate_to_<name>      │    │
│    │                                           │                     │    │
│    │  ┌────────────────────────────────────────▼──────────────────┐  │    │
│    │  │              WorkerRegistry + ThreadPoolExecutor           │  │    │
│    │  │                                                           │  │    │
│    │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐               │  │    │
│    │  │  │ Worker A │  │ Worker B │  │ Worker C │  ...           │  │    │
│    │  │  │ (coder)  │  │ (tester) │  │ (docs)   │               │  │    │
│    │  │  └────┬─────┘  └────┬─────┘  └────┬─────┘               │  │    │
│    │  └───────┼─────────────┼─────────────┼──────────────────────┘  │    │
│    └──────────┼─────────────┼─────────────┼──────────────────────────┘    │
│               │             │             │                               │
│          subprocess    subprocess    subprocess                           │
│               │             │             │                               │
│    ┌──────────▼─────────────▼─────────────▼──────────────────────────┐   │
│    │                  INTEGRATED WORKER CORE INSTANCES                  │   │
│    │                     (External Processes)                          │   │
│    │                                                                   │   │
│    │   - Autonomous Coding Agent (LiteLLM + provider detection)       │   │
│    │   - File System Access, Terminal Commands, Code Generation       │   │
│    └───────────────────────────────┬───────────────────────────────────┘   │
│                                    │                                       │
│                                    ▼                                       │
│    ┌───────────────────────────────────────────────────────────────────┐   │
│    │                  ANTIGRAVITY MANAGER (Rust Proxy)                  │   │
│    │        /v1/messages (Claude native)  |  /v1/chat/completions      │   │
│    └───────────────────────────────────────────────────────────────────┘   │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## The Manager-Worker Pattern

### Why This Pattern?

Traditional AI coding assistants directly execute code when you ask. GOrchestrator uses a **two-tier architecture** for better results:

| Layer | Role | Benefit |
|-------|------|---------|
| **Manager** | Understands, plans, reviews, coordinates | Better requirement analysis, multi-worker orchestration |
| **Workers** | Execute, code, run commands | Focused execution, parallel task completion |

### Separation of Concerns

```
┌─────────────────────────────────────────────────────────────┐
│                    MANAGER AGENT                             │
├─────────────────────────────────────────────────────────────┤
│ Responsibilities:                                           │
│ + Understand user requirements                              │
│ + Ask clarifying questions                                  │
│ + Decide WHICH worker(s) to delegate to                     │
│ + Formulate clear task descriptions                         │
│ + Coordinate parallel worker execution                      │
│ + Review and explain worker output                          │
│ + Maintain conversation context                             │
│                                                             │
│ Does NOT:                                                   │
│ - Write code directly                                       │
│ - Execute terminal commands                                 │
│ - Modify files                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                    delegate_to_<name>
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
┌──────────────────────────┐ ┌──────────────────────────┐
│      WORKER "coder"      │ │     WORKER "tester"      │
├──────────────────────────┤ ├──────────────────────────┤
│ + Write and modify code  │ │ + Write and run tests    │
│ + Execute commands       │ │ + Execute commands       │
│ + Create/delete files    │ │ + Analyze coverage       │
│ + Report results         │ │ + Report results         │
│                          │ │                          │
│ Does NOT:                │ │ Does NOT:                │
│ - Talk to user directly  │ │ - Talk to user directly  │
│ - Make arch decisions    │ │ - Make arch decisions     │
│ - Keep conversation      │ │ - Keep conversation      │
└──────────────────────────┘ └──────────────────────────┘
```

---

## Provider-Aware LLM Routing (LiteLLM)

Both Manager and Worker use **LiteLLM** with `custom_llm_provider` for unified provider-aware routing. No separate SDKs needed -- LiteLLM handles native API format for each provider automatically.

### How It Works

```python
# config.py: detect_provider()
"claude-*"    → "anthropic"   # LiteLLM → POST /v1/messages
"gpt-*"       → "openai"      # LiteLLM → POST /v1/chat/completions
"o1-*"        → "openai"      # LiteLLM → POST /v1/chat/completions
"gemini-*"    → "google"      # LiteLLM → Gemini API format
"deepseek-*"  → "openai"      # LiteLLM → POST /v1/chat/completions
```

### Manager Agent Routing

```
┌────────────────────────────────────────────────────────────────────┐
│                    MANAGER LLM ROUTING (LiteLLM)                    │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  _call_llm()                                                       │
│     │                                                              │
│     ├── detect_provider(model_name)  → "anthropic" / "openai" /..  │
│     ├── strip_provider_prefix(model_name)                          │
│     │                                                              │
│     └── litellm.completion(                                        │
│              model=model_name,                                     │
│              messages=[msg.to_dict() for msg in self.messages],    │
│              api_base=config["api_base"],                          │
│              api_key=config["api_key"],                            │
│              custom_llm_provider=provider,  # "anthropic"/"openai" │
│              tools=self._build_worker_tools(),                     │
│              thinking={...},  # for *-thinking models              │
│          )                                                         │
│                                                                    │
│  LiteLLM handles:                                                  │
│  - Native API format per provider (messages vs chat/completions)   │
│  - URL suffix (/v1/messages or /v1/chat/completions)               │
│  - Response normalization to OpenAI format                         │
│  - Extended thinking parameter forwarding                          │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Worker Agent Routing

The integrated Worker Core also uses LiteLLM with its own `_detect_provider()` function to set the correct `custom_llm_provider` when routing through the proxy. Both Manager and Worker use the same library and same pattern.

### Why LiteLLM (Not Dual SDK)

| Before (Dual SDK) | After (LiteLLM) |
|---|---|
| 2 SDKs (OpenAI + Anthropic) | 1 library (LiteLLM) |
| 2 `_call_*` methods | 1 `_call_llm` method |
| 6 helper classes (Normalized*) | 0 helper classes |
| Manual message format conversion | LiteLLM handles automatically |
| Manual URL suffix management | LiteLLM handles automatically |
| ~150 lines routing code | ~20 lines |

---

## Multi-Worker Architecture

### WorkerRegistry

Workers are managed by `WorkerRegistry` (persisted in `.gorchestrator/workers.json`):

```python
@dataclass
class WorkerConfig:
    name: str                    # Unique identifier (e.g., "coder")
    model: str                   # LLM model name
    profile: str                 # Mini-SWE config profile (e.g., "live")
    active: bool = False         # Whether this worker is currently active
    api_base: str | None = None  # Per-worker API endpoint override
    api_key: str | None = None   # Per-worker API key override
```

### Parallel Execution

When the Manager delegates to multiple workers, tasks run in parallel via `ThreadPoolExecutor`:

```
Manager: "I'll delegate coding to 'coder' and testing to 'tester'."

    ThreadPoolExecutor
    ├── Thread 1: _execute_worker_task("Create app.py...", worker_config=coder)
    │             └── subprocess: Mini-SWE-GOCore (model=claude-opus, profile=live)
    │
    └── Thread 2: _execute_worker_task("Write tests...", worker_config=tester)
                  └── subprocess: Mini-SWE-GOCore (model=claude-opus, profile=livesweagent)
```

### Primary Worker Concept

- One worker is the **primary** -- its model and profile are synced to `.env`
- Multiple workers can be **active** simultaneously
- The Manager gets a `delegate_to_<name>` tool for each active worker
- Worker output is tagged with `[worker_name]` prefix in verbose/compact modes

---

## Sub-Manager Advisory System

### Mixture of Agents Pattern

Sub-Managers are expert advisor AI agents that the Manager consults before making decisions. They provide specialized analysis (architecture review, security audit, code review) without directly executing tasks.

```
┌─────────────────────────────────────────────────────────────────┐
│                    MIXTURE OF AGENTS FLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User: "Refactor the auth system"                                │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                             │
│  │  Manager Agent   │                                            │
│  │  (Orchestrator)  │                                            │
│  └────────┬────────┘                                             │
│           │ Consult active sub-managers                          │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────────────┐        │
│  │              SubManagerRegistry                      │        │
│  │                                                      │        │
│  │  ┌──────────────┐  ┌──────────────┐                 │        │
│  │  │  architect    │  │  security    │  (active)       │        │
│  │  │  "Review      │  │  "Check for  │                 │        │
│  │  │   structure"  │  │   vulns"     │                 │        │
│  │  └──────┬───────┘  └──────┬───────┘                 │        │
│  │         │                  │                          │        │
│  │         ▼                  ▼                          │        │
│  │  ┌──────────────┐  ┌──────────────┐                 │        │
│  │  │ LiteLLM call │  │ LiteLLM call │  (parallel)     │        │
│  │  └──────┬───────┘  └──────┬───────┘                 │        │
│  │         │                  │                          │        │
│  │         ▼                  ▼                          │        │
│  │  SubManagerResponse  SubManagerResponse              │        │
│  └─────────────────────────────────────────────────────┘        │
│           │                                                      │
│           ▼                                                      │
│  Manager synthesizes advice → delegates to Worker(s)            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### SubManagerRegistry

Sub-Managers are managed by `SubManagerRegistry` (persisted in `.gorchestrator/sub_managers.json`):

```python
@dataclass
class SubManagerConfig:
    name: str                          # Unique identifier
    profile: str                       # System prompt profile
    model: str                         # LLM model name
    active: bool = False               # Whether currently active
    description: str = ""              # Human-readable description
    api_base: str | None = None        # Per-sub-manager API endpoint
    api_key: str | None = None         # Per-sub-manager API key
    parallel_llms: list[dict] = []     # Parallel LLM pool config
```

### Per-Sub-Manager LLM Pool

Each sub-manager can have its own parallel LLM pool. When queried, the sub-manager runs the same prompt through multiple LLMs simultaneously and synthesizes the best answer:

```
Sub-Manager "architect" with parallel LLMs:
    ├── Primary: claude-sonnet-4 (main model)
    ├── LLM Pool:
    │   ├── "gpt4o" → gpt-4o
    │   └── "gemini" → gemini-2.0-flash
    │
    Query → Run all 3 in parallel → Synthesize best response
```

---

## Parallel LLM Pool

### LLMPool Architecture

The `LLMPool` class (`src/core/llm_pool.py`) manages a collection of LLM configurations that can be queried in parallel using `ThreadPoolExecutor`.

```python
@dataclass
class LLMConfig:
    name: str                          # Unique identifier (e.g., "gpt4o")
    model: str                         # Model name (e.g., "gpt-4o")
    api_base: str | None = None        # API endpoint override
    api_key: str | None = None         # API key override

class LLMPool:
    def add(name, model, api_base, api_key) -> LLMConfig
    def remove(name) -> bool
    def execute_parallel(messages, on_response) -> list[LLMResponse]
```

### Parallel Execution Flow

```
execute_parallel(messages, system_prompt)
    │
    ├── ThreadPoolExecutor
    │   ├── Thread 1: litellm.completion(model="gpt-4o", ...)
    │   ├── Thread 2: litellm.completion(model="gemini-2.0-flash", ...)
    │   └── Thread 3: litellm.completion(model="deepseek-chat", ...)
    │
    └── Collect LLMResponse objects
        ├── LLMResponse(name="gpt4o", content="...", success=True)
        ├── LLMResponse(name="gemini", content="...", success=True)
        └── LLMResponse(name="deepseek", content="...", error="timeout")
```

### Usage Contexts

LLMPool is used in two contexts:
1. **Manager LLM Pool**: The Manager itself can query multiple LLMs in parallel
2. **Sub-Manager LLM Pool**: Each sub-manager can have its own pool for advisory queries

---

## Team Management

### Team Concept

Teams are saved combinations of a Manager profile and a set of Sub-Managers. Activating a team sets the Manager's profile and activates the specified sub-managers in one step.

```
┌──────────────────────────────────────────────────────┐
│                  TEAM: "review-team"                   │
├──────────────────────────────────────────────────────┤
│                                                       │
│  Manager Profile: "code-review"                       │
│                                                       │
│  Sub-Managers:                                        │
│    ● architect  (architecture review)                 │
│    ● security   (security audit)                      │
│    ● reviewer   (code quality)                        │
│                                                       │
│  /team activate review-team                           │
│    → Sets Manager profile to "code-review"            │
│    → Activates architect, security, reviewer          │
│    → Deactivates all other sub-managers               │
│                                                       │
└──────────────────────────────────────────────────────┘
```

### TeamRegistry

Teams are managed by `TeamRegistry` (persisted in `.gorchestrator/teams.json`):

```python
@dataclass
class TeamConfig:
    name: str                      # Unique identifier
    manager_profile: str           # Manager system prompt profile
    sub_managers: list[str] = []   # List of sub-manager names to activate

class TeamRegistry:
    def add(name, manager_profile, sub_managers) -> TeamConfig
    def remove(name) -> bool
    def activate(name, sub_manager_registry) -> bool  # Sets profile + activates SMs
    def deactivate(sub_manager_registry) -> None       # Deactivates all SMs
```

---

## Component Details

### 1. Session Engine (`src/core/engine.py`)

The Session Engine is the main orchestrator that manages the interaction loop.

```python
class SessionEngine:
    """Orchestrates User <-> Manager <-> Worker interactions."""

    def __init__(self):
        self.worker_registry = WorkerRegistry(...)  # Worker profiles
        self.manager = ManagerAgent(...)             # LLM-powered agent
        self.ui = ConsoleUI(...)                     # Rich terminal

    def start_interactive_mode(self):
        """Main loop: get input -> process -> display"""
        self.ui.print_dashboard(...)  # Show startup dashboard
        while running:
            user_input = ui.get_user_input()
            if is_slash_command(user_input):
                handle_slash_command(user_input)
            else:
                response = manager.chat(user_input)
                display_response(response)
```

**Responsibilities:**
- Initialize and manage the Manager Agent and WorkerRegistry
- Handle all slash commands (session, config, worker, safety)
- Route user input to appropriate handlers
- Manage session persistence with unique IDs and random names
- Coordinate UI updates and dashboard display
- Create git checkpoints before worker tasks
- Auto-save on exit, Ctrl+C, EOFError

### 2. Manager Agent (`src/core/manager.py`)

The Manager Agent is an LLM-powered conversational agent with LiteLLM-based unified routing and dynamic tool calling.

```python
class ManagerAgent:
    def __init__(self, settings, worker_registry, on_worker_output, on_thinking):
        self.settings = settings
        self.worker = AgentWorker(settings)
        self.worker_registry = worker_registry  # For dynamic tools
        self.messages = []

        self.on_worker_output = on_worker_output  # fn(line, worker_name)
        self.on_thinking = on_thinking

    def chat(self, user_message: str) -> ManagerResponse:
        self.messages.append(user_message)
        response = self._call_llm()  # LiteLLM unified routing
        if response.has_tool_calls:
            results = self._handle_tool_calls(response.tool_calls)
        return response
```

**Key Features:**
- LiteLLM-based unified routing: single `_call_llm()` for all providers
- Dynamic tool system: `delegate_to_<name>` for each active worker
- Conversation history in OpenAI message format (LiteLLM handles conversion)
- Extended thinking support for `*-thinking` models
- Worker output tagged with `[worker_name]` via callback
- Parallel worker execution via ThreadPoolExecutor

### 3. Agent Worker (`src/core/worker.py`)

The Worker wraps the integrated worker core subprocess with per-worker API override support.

```python
class AgentWorker:
    def run_task(self, task, model, profile,
                 api_base=None, api_key=None,
                 on_output=None) -> TaskResult:
        env = self._build_env(api_base_override=api_base,
                              api_key_override=api_key)
        process = subprocess.Popen(
            ["uv", "run", "mini", "--headless",
             "--profile", profile, "--model", model,
             "--task", task],
            env=env, stdout=subprocess.PIPE,
        )
        for line in process.stdout:
            on_output(line)
        return TaskResult(...)
```

**Key Features:**
- Spawns integrated worker core as subprocess
- Per-worker API override (`api_base`, `api_key` parameters)
- Base URL passed as-is -- LiteLLM adds correct suffix automatically
- Streams output in real-time
- Returns structured TaskResult
- Graceful shutdown on Ctrl+C
- Configurable timeout (`WORKER_TIMEOUT`)

### 4. Sub-Manager Registry (`src/core/sub_manager.py`)

Manages expert advisor AI agents that provide specialized analysis before task delegation.

```python
class SubManagerRegistry:
    def __init__(self, registry_file: Path):
        self._registry: dict[str, SubManagerConfig] = {}
        self._load()

    def add(name, profile, model, description) -> SubManagerConfig
    def remove(name) -> bool
    def set_active(name) / set_inactive(name) -> bool
    def activate_only(names: list[str])  # Activate specific, deactivate rest
    def get_active() -> list[SubManagerConfig]
    def add_parallel_llm(name, llm_name, model) -> bool
    def remove_parallel_llm(name, llm_name) -> bool
```

**Key Features:**
- CRUD operations with JSON persistence
- Per-sub-manager parallel LLM pools
- Profile-based system prompts from `src/worker_core/.miniswe/configs/sub_managers/`
- LiteLLM-based provider-aware routing per sub-manager
- Name sanitization via `SANITIZE_RE`

### 5. LLM Pool (`src/core/llm_pool.py`)

Manages parallel multi-LLM execution for both Manager and Sub-Managers.

```python
class LLMPool:
    def __init__(self, registry_file: Path | None = None):
        self._llms: dict[str, LLMConfig] = {}

    def add(name, model, api_base, api_key) -> LLMConfig
    def remove(name) -> bool
    def execute_parallel(messages, system_prompt, on_response) -> list[LLMResponse]
    def to_dict_list() / from_dict_list(data)  # Serialization
```

**Key Features:**
- File-backed or in-memory mode
- Parallel execution via `ThreadPoolExecutor`
- Per-LLM provider detection and routing
- Callback support for streaming responses
- Error isolation (one LLM failure doesn't affect others)

### 6. Team Registry (`src/core/team.py`)

Manages saved Manager + Sub-Manager combinations as reusable teams.

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

**Key Features:**
- One-step activation (sets profile + activates sub-managers)
- Member management (add/remove sub-managers from teams)
- JSON persistence in `.gorchestrator/teams.json`

### 7. Console UI (`src/ui/console.py`)

Rich-based terminal interface with dashboard, autocomplete, and role-specific formatting.

```python
class ConsoleUI:
    def print_dashboard(self, info):           # Startup dashboard panel
    def display_user_message(self, msg):       # Green panel
    def display_manager_message(self, msg):    # Cyan panel
    def display_worker_step(self, entry, worker_name):  # [name] prefix
    def display_worker_result(self, result):   # Result panel
    def get_user_input(self):                  # prompt_toolkit + autocomplete
```

**Key Features:**
- Rich Panel dashboard at startup (session, manager, workers, mode)
- NestedCompleter for tab-completion of all slash commands
- SafeFileHistory for persistent input history
- Worker output tagged with `[worker_name]` in verbose/compact modes
- Ctrl+J for multi-line input

---

## Data Flow

### Complete Request Flow

```
User          SessionEngine      ManagerAgent       AgentWorker(s)    Mini-SWE
  │                 │                  │                 │               │
  │ "Create app"    │                  │                 │               │
  │────────────────►│                  │                 │               │
  │                 │  chat(msg)       │                 │               │
  │                 │─────────────────►│                 │               │
  │                 │                  │ detect_provider │               │
  │                 │                  │ _call_llm()     │               │
  │                 │                  │═══════════╗     │               │
  │                 │                  │           ║     │               │
  │                 │                  │◄══════════╝     │               │
  │                 │                  │ tool_calls:     │               │
  │                 │                  │ delegate_to_    │               │
  │                 │                  │ coder + tester  │               │
  │                 │                  │                 │               │
  │                 │ checkpoint()     │                 │               │
  │                 │◄─────────────────│                 │               │
  │                 │                  │  ThreadPool     │               │
  │                 │                  │  ┌─────────────►│ subprocess x2 │
  │                 │                  │  │  run_task()  │──────────────►│
  │                 │                  │  │              │               │
  │ [coder] Step 1  │  on_output()     │  │              │  streaming    │
  │◄────────────────│◄─────────────────│◄─┤              │◄──────────────│
  │ [tester] Step 1 │                  │  │              │               │
  │◄────────────────│◄─────────────────│◄─┤              │               │
  │                 │                  │  │              │               │
  │                 │                  │  │ TaskResult x2│               │
  │                 │                  │◄─┘◄─────────────│◄──────────────│
  │                 │                  │                 │               │
  │                 │                  │ _call_llm()     │               │
  │                 │                  │ (with results)  │               │
  │                 │                  │═══════════╗     │               │
  │                 │                  │◄══════════╝     │               │
  │                 │  ManagerResponse │                 │               │
  │ [Manager msg]   │◄─────────────────│                 │               │
  │◄────────────────│                  │                 │               │
  │                 │ auto-save()      │                 │               │
```

---

## Session Management

### Unique Session IDs

Each session gets a unique identifier composed of a random name and a short UUID:

```
bold-phoenix-a1b2c3d4
swift-nebula-e5f6g7h8
```

### Per-Session Directories

```
.gorchestrator/
├── sessions/
│   ├── bold-phoenix-a1b2c3d4/
│   │   └── session.json         # Conversation history
│   ├── swift-nebula-e5f6g7h8/
│   │   └── session.json
│   └── ...
├── workers.json                 # Worker registry (persistent)
└── gorchestrator.log            # Application log
```

### Session Lifecycle

```
1. START
   └── Check for latest session
       ├── Found: auto-resume (restore history)
       └── Not found: new session with random name

2. EACH TURN
   └── User sends message → Manager responds → Auto-save

3. MANUAL OPERATIONS
   ├── /save [name]  → Save snapshot
   ├── /load [id]    → Load by ID or name
   ├── /new [name]   → Start fresh session
   └── /list         → Show all sessions

4. EXIT
   └── Auto-save via atexit / Ctrl+C / EOFError
```

### Session File Structure

```json
{
  "version": "2.0",
  "session_id": "bold-phoenix-a1b2c3d4",
  "saved_at": "2025-01-15T10:30:00.000000",
  "mode": "auto",
  "manager_history": [
    {
      "role": "system",
      "content": "You are GOrchestrator...",
      "timestamp": "2025-01-15T10:00:00.000000"
    },
    {
      "role": "user",
      "content": "Create a Flask app",
      "timestamp": "2025-01-15T10:01:00.000000"
    }
  ]
}
```

---

## Checkpoint System

GOrchestrator creates git checkpoints before each Worker task execution, enabling easy rollback.

```
1. User requests a task
2. Manager decides to delegate to Worker
3. Engine creates git checkpoint (tag: gorchestrator-checkpoint-<timestamp>)
4. Worker executes task (modifies files)
5. If something goes wrong:
   └── /undo → reverts to last checkpoint
   └── /checkpoints → lists all available checkpoints
```

---

## Dynamic Tool System

### How Tools Are Built

Instead of a single static `delegate_to_worker` tool, the Manager gets dynamically generated tools based on active workers:

```python
def _build_worker_tools(self) -> list[dict]:
    tools = []
    for wc in worker_registry.get_active_workers():
        tool = {
            "type": "function",
            "function": {
                "name": f"delegate_to_{wc.name}",
                "description": f"Delegate to Worker '{wc.name}' "
                               f"(model: {wc.model}, profile: {wc.profile})...",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_description": {"type": "string"},
                        "context": {"type": "string"}
                    },
                    "required": ["task_description"]
                }
            }
        }
        tools.append(tool)
    return tools
```

### System Prompt Integration

The Manager's system prompt dynamically lists active workers:

```
You have the following Workers available:
- 'coder' (model: claude-opus-4, profile: live) → use delegate_to_coder
- 'tester' (model: claude-opus-4, profile: livesweagent) → use delegate_to_tester
```

---

## Environment Variable Injection

When the Worker spawns the integrated worker core, it injects only two environment variables:

```python
def get_agent_env(self) -> dict[str, str]:
    return {
        "MINI_API_BASE": self.PROXY_URL,   # API endpoint (no suffix)
        "MINI_API_KEY": self.PROXY_KEY,     # API key for proxy auth
    }
```

Per-worker API overrides (`api_base`, `api_key` from WorkerConfig) take precedence when set via `/worker api <name> <url> [key]`. Base URLs are passed as-is -- LiteLLM handles URL suffixes automatically (`/v1/messages` for Anthropic, `/v1/chat/completions` for OpenAI).

The integrated worker core's LiteLLM handles provider routing internally using its own `_detect_provider()` function -- the same pattern used by the Manager.

---

<p align="center">
  <strong>Understanding the architecture helps you debug issues and extend functionality.</strong>
</p>

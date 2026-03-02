<p align="center">
  <img src="docs/assets/logo.png" alt="GOrchestrator Logo" width="200"/>
</p>

<h1 align="center">GOrchestrator</h1>

<p align="center">
  <strong>Your AI Software Team in a Terminal</strong>
</p>

<p align="center">
  <em>A multi-worker AI orchestrator with LiteLLM-based unified LLM routing, parallel task execution, and rich session management</em>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#the-ecosystem">Ecosystem</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#usage">Usage</a> •
  <a href="#multi-worker-system">Multi-Worker</a> •
  <a href="#documentation">Docs</a>
</p>

---

## What is GOrchestrator?

GOrchestrator is an **Intelligent AI Agent Manager** that acts as your personal Software Architect. You have a conversation with a smart Manager agent who understands your requirements, plans solutions, and delegates coding tasks to one or more Worker agents -- in parallel when needed.

```
┌─────────────────────────────────────────────────────────────┐
│  You: "Create a REST API and write tests for it"            │
│                                                             │
│  Manager: "I'll split this into two tasks and delegate      │
│     to both workers in parallel..."                         │
│                                                             │
│  [coder]  → Creates app.py with CRUD endpoints              │
│  [tester] → Writes test_app.py with pytest tests            │
│                                                             │
│  Manager: "Done! app.py has 4 endpoints and test_app.py     │
│     has 12 test cases. Run with `flask run`"                │
└─────────────────────────────────────────────────────────────┘
```

<p align="center">
  <img src="docs/assets/demo.gif" alt="GOrchestrator Demo" width="700"/>
</p>

## Features

| Feature | Description |
|---------|-------------|
| **Multi-Worker Parallel Execution** | Multiple Worker agents run tasks simultaneously via ThreadPoolExecutor |
| **Mixture of Agents (Sub-Managers)** | Expert advisor AI agents provide specialized analysis before task delegation |
| **Parallel LLM Pool** | Run multiple LLMs in parallel and synthesize the best answer |
| **Team Management** | Save Manager + Sub-Manager combinations as reusable teams |
| **Provider-Aware Native Routing** | Claude models use Anthropic native API; OpenAI models use OpenAI API -- automatically |
| **Per-Worker API Endpoints** | Each worker can target a different API endpoint and key |
| **Rich Dashboard** | Startup dashboard shows session, manager, workers, mode at a glance |
| **Session Management** | Unique session IDs, random names, auto-save, auto-resume, per-session directories |
| **Git Checkpoint System** | Automatic git checkpoints before Worker tasks; `/undo` to revert |
| **Dynamic Tool System** | Manager gets `delegate_to_<name>` tools for each active worker |
| **Extended Thinking** | Supports Claude thinking models (`*-thinking`) with extended reasoning |
| **Autocomplete** | Tab-completion for all slash commands and sub-commands |
| **Multi-line Input** | Ctrl+J for new lines; paste multi-line text directly |
| **Config Persistence** | Runtime changes (`/model`, `/config set`) are saved to `.env` |
| **Confirmation Mode** | `/confirm on` to review Worker tasks before execution |

## The Ecosystem

GOrchestrator is part of a three-component AI development ecosystem:

```
┌───────────────────────────────────────────────────────────────────────────┐
│                          THE AI DEV ECOSYSTEM                             │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐     │
│  │   ANTIGRAVITY   │    │   GORCHESTRATOR  │    │  MINI-SWE-GOCORE │     │
│  │    MANAGER      │    │   (The Boss)     │    │  (The Workers)   │     │
│  │                 │    │                  │    │                  │     │
│  │  Rust Proxy     │◄───│  Architect AI    │───►│  Coding Agents   │     │
│  │  /v1/messages   │    │  Multi-Worker    │    │  Code Execution  │     │
│  │  /v1/chat/comp. │    │  Task Planning   │    │  File I/O        │     │
│  └─────────────────┘    └──────────────────┘    └──────────────────┘     │
│          ▲                       │                       ▲                │
│          │              Provider Detection               │                │
│          │         ┌─────────┴──────────┐                │                │
│          │         ▼                    ▼                 │                │
│     /v1/messages              /v1/chat/completions        │                │
│     (Claude native)           (OpenAI compatible)         │                │
│                                                           │                │
│          └───────────────────────────────────────────────┘                │
│                            LLM API Calls                                  │
└───────────────────────────────────────────────────────────────────────────┘
```

| Component | Role | Repository |
|-----------|------|------------|
| **Antigravity Manager** | Rust proxy with `/v1/messages` + `/v1/chat/completions` endpoints | [github.com/lbjlaq/Antigravity-Manager](https://github.com/lbjlaq/Antigravity-Manager) |
| **GOrchestrator** | Intelligent Architect Agent with multi-worker orchestration (You are here) | This repository |
| **Mini-SWE-GOCore** | Autonomous Coding Agent (integrated as worker core) | Included in `src/worker_core/` |

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Running instance of an API proxy (Antigravity Manager, CLIProxyAPI, etc.)

### Installation

```bash
git clone https://github.com/orhaniscoding/GOrchestrator.git
cd GOrchestrator

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your API endpoint and key

# Run GOrchestrator
uv run python main.py
```

### First Run

On startup you see the dashboard:

```
┌────────────────────── GOrchestrator ──────────────────────┐
│  Session: bold-phoenix (new)                              │
│  Manager: claude-sonnet-4-20250514 @ http://127.0.0.1:8045│
│                                                           │
│  Workers:                                                 │
│    ● default  (claude-sonnet-4-20250514, live) [primary]  │
│                                                           │
│  Mode: Quiet | Confirm: OFF                               │
└───────────────────────────────────────────────────────────┘

You>
```

## Usage

### Chatting with the Manager

The Manager understands natural language:

```bash
# Ask questions (no Worker needed)
You> What's the difference between REST and GraphQL?

# Request code tasks (Worker will be used)
You> Create a FastAPI app with user authentication

# Request fixes
You> Fix the bug in src/app.py line 42

# Multi-line input (Ctrl+J for new line)
You> Here is the error:     [Ctrl+J]
     TypeError: 'NoneType' object is not iterable
```

### Slash Commands

#### Session Commands

| Command | Alias | Description |
|---------|-------|-------------|
| `/save [name]` | `/s` | Save current session |
| `/load [id or name]` | | Load session by ID or name (shows list if no arg) |
| `/list` | `/l` | List all saved sessions |
| `/new [name]` | | Start a new session (random name if omitted) |
| `/clear` | | Clear conversation and start new session |
| `/clearterminal` | `/ct` | Clear terminal screen only |
| `/history` | | Show full conversation history |

#### Display Commands

| Command | Description |
|---------|-------------|
| `/verbose` | Show detailed Worker output |
| `/quiet` | Show summarized Worker output |

#### Config Commands

| Command | Description |
|---------|-------------|
| `/model [manager\|worker] <name>` | Change model (saved to .env) |
| `/config show` | Show current configuration |
| `/config reload` | Reload .env file |
| `/config validate` | Check config for issues |
| `/config set <KEY> <VALUE>` | Set a config value (saved to .env) |

**Config aliases:**
- `/config set manager <model>` sets `ORCHESTRATOR_MODEL`
- `/config set worker <model>` sets `WORKER_MODEL`

#### Worker Management

| Command | Alias | Description |
|---------|-------|-------------|
| `/worker list` | `/w list` | List all worker profiles |
| `/worker add <name> [model] [profile]` | | Add a new worker |
| `/worker remove <name>` | | Remove a worker |
| `/worker set <name> active` | | Activate a worker |
| `/worker set <name> inactive` | | Deactivate a worker |
| `/worker set <name> primary` | | Set as primary worker (.env sync) |
| `/worker show <name>` | | Show worker details |
| `/worker model <name> <model>` | | Change a worker's model |
| `/worker profile <name> <profile>` | | Change a worker's profile |
| `/worker api <name> <url> [key]` | | Set per-worker API endpoint |

#### Sub-Manager Management (Mixture of Agents)

| Command | Alias | Description |
|---------|-------|-------------|
| `/submanager list` | `/sm list` | List all sub-managers |
| `/submanager add <name> <profile> [model]` | | Add a new sub-manager advisor |
| `/submanager remove <name>` | | Remove a sub-manager |
| `/submanager set <name> active\|inactive` | | Activate/deactivate a sub-manager |
| `/submanager show <name>` | | Show sub-manager details |
| `/submanager model <name> <model>` | | Change sub-manager's model |
| `/submanager api <name> <base> [key]` | | Set sub-manager's API endpoint |
| `/submanager llm <name> list` | | List parallel LLMs for a sub-manager |
| `/submanager llm <name> add <llm> <model>` | | Add a parallel LLM to sub-manager |
| `/submanager llm <name> remove <llm>` | | Remove a parallel LLM |

#### Team Management

| Command | Description |
|---------|-------------|
| `/team list` | List all teams |
| `/team add <name> <profile> [sm1,sm2,...]` | Create a team with manager profile and sub-managers |
| `/team remove <name>` | Remove a team |
| `/team activate <name>` | Activate a team (sets profile + sub-managers) |
| `/team deactivate` | Deactivate all teams |
| `/team show <name>` | Show team details |
| `/team addmember <team> <sm>` | Add sub-manager to team |
| `/team removemember <team> <sm>` | Remove sub-manager from team |
| `/team manager <team> <profile>` | Change team's manager profile |

#### Manager LLM Pool

| Command | Description |
|---------|-------------|
| `/manager llm list` | List parallel LLMs for the Manager |
| `/manager llm add <name> <model> [api_base] [api_key]` | Add a parallel LLM |
| `/manager llm remove <name>` | Remove a parallel LLM |

#### Safety Commands

| Command | Description |
|---------|-------------|
| `/confirm on\|off` | Ask before Worker executes |
| `/undo` | Revert last Worker changes (git) |
| `/checkpoints` | List available git checkpoints |

#### Other

| Command | Alias | Description |
|---------|-------|-------------|
| `/help` | `/h` | Show help information |
| `exit` | `q` | Exit the application |

### Input Tips

- **Tab**: Autocomplete slash commands and sub-commands
- **Arrow Up/Down**: Browse input history
- **Ctrl+J**: Insert new line (multi-line input)
- **Multi-line paste**: Paste multi-line text directly

## Multi-Worker System

GOrchestrator supports multiple Worker agents that can execute tasks in parallel.

### Adding Workers

```bash
# Add a worker with a name, model, and profile
You> /worker add coder claude-sonnet-4-20250514 live
You> /worker add tester claude-sonnet-4-20250514 livesweagent

# Activate workers
You> /worker set coder active
You> /worker set tester active

# Set per-worker API endpoint (e.g., for litellm with z.ai)
You> /worker api tester https://api.z.ai sk-zai-key
```

### How It Works

- Multiple workers can be **active** simultaneously
- The **primary** worker's settings are written to `.env`
- The Manager automatically gets `delegate_to_<name>` tools for each active worker
- The Manager chooses which worker(s) to use based on the task
- Workers run in parallel via `ThreadPoolExecutor`
- Each worker can have its own API endpoint and key

### Example

```
You> Create app.py and write tests for it

Manager: I'll delegate coding to 'coder' and testing to 'tester'
  in parallel...

  [coder]  Step 1... Step 2... Step 3...
  [tester] Step 1... Step 2...

  Worker Result [coder]:  SUCCESS | Steps: 3 | $0.02
  Worker Result [tester]: SUCCESS | Steps: 2 | $0.01

Manager: Done! Created app.py with 4 endpoints and
test_app.py with 12 test cases covering all routes.
```

## Configuration

Edit `.env` to configure GOrchestrator:

```bash
# Manager Agent (the "Boss" that talks to you)
ORCHESTRATOR_MODEL=claude-sonnet-4-20250514
ORCHESTRATOR_API_BASE=http://127.0.0.1:8045
ORCHESTRATOR_API_KEY=sk-your-key

# Default Worker Agent (Integrated Worker Core)
WORKER_MODEL=claude-sonnet-4-20250514
WORKER_PROFILE=live
AGENT_PATH=src/worker_core
PROXY_URL=http://127.0.0.1:8045
PROXY_KEY=sk-your-key

# Application
VERBOSE_WORKER=false
MAX_WORKER_ITERATIONS=5
WORKER_TIMEOUT=600
```

### Provider-Aware Routing

GOrchestrator automatically detects the LLM provider from the model name:

| Model Pattern | Provider | API Format |
|---------------|----------|------------|
| `claude-*` | Anthropic | Native `/v1/messages` |
| `gpt-*`, `o1-*` | OpenAI | `/v1/chat/completions` |
| `gemini-*` | Google | OpenAI-compatible |
| `deepseek-*` | DeepSeek | OpenAI-compatible |
| Others | OpenAI | `/v1/chat/completions` |

No manual provider configuration is needed. Both Manager and Worker use LiteLLM with automatic provider detection via `custom_llm_provider`.

### Runtime Configuration

All config changes made at runtime are persisted:

```bash
# Change models (saved to .env)
You> /model manager claude-opus-4-6-thinking
You> /model worker claude-sonnet-4-20250514

# Set any config value
You> /config set MAX_WORKER_ITERATIONS 10
You> /config set VERBOSE_WORKER true
```

### Worker Profiles

The `WORKER_PROFILE` setting determines which configuration the Worker agent uses. Profiles are YAML files in `src/worker_core/.miniswe/configs/`:

| Profile | Best For |
|---------|----------|
| `live` | General purpose tasks, quick edits |
| `livesweagent` | Complex software engineering tasks, debugging, refactoring |

Create custom profiles by copying an existing YAML and modifying it. See the [Setup Guide](docs/setup_guide.md#worker-profiles) for details.

## Documentation

| Document | Description |
|----------|-------------|
| [Setup Guide](docs/setup_guide.md) | Complete installation walkthrough |
| [User Guide](docs/user_guide.md) | How to use GOrchestrator effectively |
| [Architecture](docs/architecture.md) | Technical architecture deep-dive |
| [Developer Guide](docs/developer_guide.md) | Contributing and customization |

## Project Structure

```
GOrchestrator/
├── main.py                 # CLI entry point
├── pyproject.toml          # Dependencies
├── .env.example            # Configuration template
├── src/
│   ├── core/
│   │   ├── __init__.py     # Public API exports
│   │   ├── config.py       # Settings, provider detection, env persistence
│   │   ├── manager.py      # Manager Agent (LiteLLM unified routing)
│   │   ├── worker.py       # Worker subprocess wrapper
│   │   ├── engine.py       # Session engine, WorkerRegistry, slash commands
│   │   ├── sub_manager.py  # Sub-Manager advisory agents (Mixture of Agents)
│   │   ├── llm_pool.py     # Parallel multi-LLM execution pool
│   │   └── team.py         # Team management (Manager + Sub-Manager combos)
│   ├── commands/
│   │   ├── parser.py       # Command parser and validator
│   │   ├── handlers.py     # Command handlers for all sources
│   │   ├── completer.py    # Tab completion system
│   │   └── help.py         # Help system
│   ├── ui/
│   │   └── console.py      # Rich terminal UI, dashboard, autocomplete
│   ├── utils/
│   │   └── parser.py       # Worker JSON log parser
│   └── worker_core/        # Integrated coding agent (Mini-SWE-GOCore)
│       ├── minisweagent/    # Agent engine (models, agents, config, etc.)
│       └── .miniswe/        # Runtime configs and profiles
├── tests/                  # ~194 unit tests
│   ├── test_config.py      # Settings + provider detection tests
│   ├── test_engine.py      # Session engine + worker management tests
│   ├── test_manager.py     # Manager agent + LiteLLM routing tests
│   ├── test_llm_pool.py    # LLM Pool CRUD, persistence, parallel exec
│   ├── test_sub_manager.py # Sub-Manager registry tests
│   ├── test_commands_parser.py # Command parser tests
│   └── test_parser.py      # Log parser tests
├── docs/                   # Documentation
│   ├── architecture.md
│   ├── user_guide.md
│   ├── setup_guide.md
│   └── developer_guide.md
└── .gorchestrator/         # Runtime data (gitignored)
    ├── sessions/           # Per-session directories
    └── workers.json        # Worker registry
```

## Contributing

We welcome contributions! Please open an issue or pull request on GitHub.

## License

MIT License - see [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Built with care for developers who want AI that works WITH them, not FOR them.</strong>
</p>

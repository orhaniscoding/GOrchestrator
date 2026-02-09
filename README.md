<p align="center">
  <img src="docs/assets/logo.png" alt="GOrchestrator Logo" width="200"/>
</p>

<h1 align="center">GOrchestrator</h1>

<p align="center">
  <strong>🚀 Your AI Software Team in a Terminal</strong>
</p>

<p align="center">
  <em>An intelligent Architect Agent that manages your coding projects through natural conversation</em>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#the-ecosystem">Ecosystem</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#usage">Usage</a> •
  <a href="#documentation">Docs</a>
</p>

---

## What is GOrchestrator?

GOrchestrator is an **Intelligent AI Agent Manager** that acts as your personal Software Architect. Instead of writing code directly, you have a conversation with a smart "Boss" agent who understands your requirements, asks clarifying questions, and delegates coding tasks to a powerful Worker agent.

```
┌─────────────────────────────────────────────────────────────┐
│  You: "Create a REST API for user management"               │
│                                                             │
│  🧠 Manager: "I'll create a Flask-based REST API with       │
│     CRUD operations. Let me delegate this to the Worker..." │
│                                                             │
│  👷 Worker: [Creates files, writes code, runs tests]        │
│                                                             │
│  🧠 Manager: "Done! I've created `app.py` with endpoints    │
│     for GET, POST, PUT, DELETE. Run with `flask run`"       │
└─────────────────────────────────────────────────────────────┘
```

<p align="center">
  <img src="docs/assets/demo.gif" alt="GOrchestrator Demo" width="700"/>
</p>

## Features

| Feature | Description |
|---------|-------------|
| 🧠 **Intelligent Manager** | LLM-powered agent that understands context and requirements |
| 👷 **Powerful Worker** | Delegates to Mini-SWE-GOCore for code execution |
| 💬 **Natural Conversation** | Chat like you would with a senior developer |
| 💾 **Session Persistence** | Save and restore conversation context |
| 🎨 **Beautiful CLI** | Rich terminal interface with role-based formatting |
| 🔧 **Configurable** | Separate models for Manager and Worker |

## The Ecosystem

GOrchestrator is part of a three-component AI development ecosystem:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         THE AI DEV ECOSYSTEM                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    │
│   │   ANTIGRAVITY   │    │  GORCHESTRATOR  │    │  MINI-SWE-CORE  │    │
│   │    MANAGER      │    │   (The Boss)    │    │  (The Worker)   │    │
│   │                 │    │                 │    │                 │    │
│   │  LiteLLM Proxy  │◄───│  Architect AI   │───►│  Coding Agent   │    │
│   │  API Gateway    │    │  Conversation   │    │  Code Execution │    │
│   │  Model Router   │    │  Task Planning  │    │  File I/O       │    │
│   └─────────────────┘    └─────────────────┘    └─────────────────┘    │
│          ▲                       ▲                       ▲              │
│          │                       │                       │              │
│          └───────────────────────┴───────────────────────┘              │
│                            LLM API Calls                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

| Component | Role | Repository |
|-----------|------|------------|
| **Antigravity Manager** | LiteLLM Proxy & API Gateway | [github.com/lbjlaq/Antigravity-Manager](https://github.com/lbjlaq/Antigravity-Manager) |
| **GOrchestrator** | Intelligent Architect Agent (You are here) | This repository |
| **Mini-SWE-GOCore** | Autonomous Coding Agent | Your Mini-SWE repo |

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Running instance of Antigravity Manager
- Configured Mini-SWE-GOCore

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/GOrchestrator.git
cd GOrchestrator

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run GOrchestrator
uv run python main.py
```

### First Run

```
┌──────────────────────────────────────────────────────────────┐
│   GOrchestrator   - Intelligent AI Agent Manager             │
└──────────────────────────────────────────────────────────────┘

ℹ Chat with the Manager Agent. Use /help for commands.

You> Hello! What can you do?

🧠 Manager: Hello! I'm GOrchestrator, your AI Software Architect.
I can help you with:
- Creating new projects and files
- Writing and modifying code
- Debugging and fixing issues
- Explaining code and concepts
- Running terminal commands

Just tell me what you need!

You> Create a simple Python web server

🧠 Manager: I'll create a simple HTTP server for you...
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

# Ask for explanations
You> Explain what the Worker just did
```

### Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help information |
| `/save [name]` | Save session (default: manual_save) |
| `/load [name]` | Load session (default: latest_session) |
| `/list` | List available sessions |
| `/clear` | Clear conversation history and screen |
| `/verbose` | Show detailed Worker output |
| `/quiet` | Show summarized Worker output |
| `/history` | Show conversation history |
| `exit` | Exit the application |

## Configuration

Edit `.env` to configure GOrchestrator:

```bash
# Manager Agent (the "Boss" that talks to you)
ORCHESTRATOR_MODEL=claude-3-5-sonnet-20241022
ORCHESTRATOR_API_BASE=http://127.0.0.1:8045
ORCHESTRATOR_API_KEY=sk-your-key

# Worker Agent (Mini-SWE-GOCore)
WORKER_MODEL=claude-3-5-sonnet-20241022
WORKER_PROFILE=live
AGENT_PATH=../Mini-SWE-GOCore

# Display settings
VERBOSE_WORKER=false
MAX_WORKER_ITERATIONS=5
WORKER_TIMEOUT=600
```

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
│   │   ├── config.py       # Settings management
│   │   ├── manager.py      # Manager Agent (LLM)
│   │   ├── worker.py       # Worker subprocess
│   │   └── engine.py       # Session orchestration
│   ├── ui/
│   │   └── console.py      # Rich terminal UI
│   └── utils/
│       └── parser.py       # Log parsing
├── tests/                  # Unit tests
│   ├── test_config.py
│   ├── test_engine.py
│   ├── test_manager.py
│   └── test_parser.py
└── docs/                   # Documentation
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Built with ❤️ for developers who want AI that works WITH them, not FOR them.</strong>
</p>

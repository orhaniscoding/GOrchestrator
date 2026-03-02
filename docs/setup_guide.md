# Setup Guide: Zero to Hero

This guide will walk you through setting up GOrchestrator with its integrated worker core and an API proxy.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Step 1: API Proxy](#step-1-api-proxy)
- [Step 2: GOrchestrator](#step-2-gorchestrator)
- [Configuration Deep Dive](#configuration-deep-dive)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, ensure you have:

| Requirement | Version | Check Command |
|-------------|---------|---------------|
| Python | 3.11+ | `python --version` |
| uv | Latest | `uv --version` |
| Git | Any | `git --version` |
| API Keys | - | Anthropic, OpenAI, etc. |

### Install uv (Recommended)

```bash
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Step 1: API Proxy

You need an API proxy that routes LLM calls. GOrchestrator works with any proxy that supports `/v1/messages` (Anthropic) and `/v1/chat/completions` (OpenAI) endpoints:

- **Antigravity Manager** (Rust-based, recommended)
- **CLIProxyAPI** / **CLIProxyAPIPlus** (Go-based)
- **Any OpenAI-compatible proxy**
- **Direct API access** (set api_base to provider's URL directly)

### Example: Antigravity Manager

```bash
git clone https://github.com/lbjlaq/Antigravity-Manager.git
cd Antigravity-Manager
# Follow the build instructions in the repository
./antigravity-manager  # Default port: 8045
```

Verify:
```bash
curl http://127.0.0.1:8045/health
```

> **Keep the proxy running!** GOrchestrator needs it for LLM calls.

---

## Step 2: GOrchestrator

GOrchestrator includes the worker core (coding agent) built-in -- no separate installation needed.

### 2.1 Clone and Install

```bash
git clone https://github.com/orhaniscoding/GOrchestrator.git
cd GOrchestrator

# Single install -- includes all dependencies (manager + worker core)
uv sync
```

### 2.2 Configure

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```bash
# ============================================================
# ORCHESTRATOR (Manager Agent) -- the LLM that talks to you
# ============================================================
ORCHESTRATOR_MODEL=claude-sonnet-4-20250514
ORCHESTRATOR_API_BASE=http://127.0.0.1:8045
ORCHESTRATOR_API_KEY=sk-your-proxy-key

# ============================================================
# WORKER (Integrated Worker Core) -- the LLM that writes code
# ============================================================
WORKER_MODEL=claude-sonnet-4-20250514
WORKER_PROFILE=live
PROXY_URL=http://127.0.0.1:8045
PROXY_KEY=sk-your-proxy-key

# ============================================================
# Application Settings
# ============================================================
VERBOSE_WORKER=false
MAX_WORKER_ITERATIONS=5
WORKER_TIMEOUT=600
```

### 2.3 Run GOrchestrator

```bash
uv run python main.py
```

You should see the startup dashboard:

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

---

## Configuration Deep Dive

### Understanding the Architecture

Both Manager and Worker use **LiteLLM** for unified provider-aware routing. The provider is auto-detected from the model name:

```
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (Manager)                    │
│                                                             │
│  ORCHESTRATOR_MODEL     = The model YOU talk to             │
│  ORCHESTRATOR_API_BASE  = Proxy endpoint                    │
│  ORCHESTRATOR_API_KEY   = Key for proxy auth                │
│                                                             │
│  Provider auto-detected from model name:                    │
│    claude-* → LiteLLM (anthropic) → /v1/messages            │
│    gpt-*   → LiteLLM (openai)    → /v1/chat/completions    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ delegates to
┌─────────────────────────────────────────────────────────────┐
│                 WORKER(S) (Integrated Worker Core)          │
│                                                             │
│  WORKER_MODEL   = Default Worker model                      │
│  PROXY_URL      = Where Worker sends LLM calls              │
│  PROXY_KEY      = Key for Worker's proxy auth               │
│                                                             │
│  Additional workers: /worker add <name> [model] [profile]   │
│  Per-worker API:     /worker api <name> <url> [key]         │
└─────────────────────────────────────────────────────────────┘
```

### Model Recommendations

| Use Case | Manager Model | Worker Model |
|----------|---------------|--------------|
| **Cost-Effective** | claude-haiku | claude-sonnet |
| **Balanced** | claude-sonnet | claude-sonnet |
| **Maximum Power** | claude-opus-thinking | claude-sonnet |

> **Tip:** The Manager handles conversation, so a faster/cheaper model works well. The Worker needs strong coding abilities.

### Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `ORCHESTRATOR_MODEL` | LLM model for Manager | claude-sonnet-4-20250514 |
| `ORCHESTRATOR_API_BASE` | API endpoint for Manager | http://127.0.0.1:8045 |
| `ORCHESTRATOR_API_KEY` | API key for Manager | sk-your-proxy-key |
| `WORKER_MODEL` | Default LLM model for Worker | claude-sonnet-4-20250514 |
| `WORKER_PROFILE` | Worker config profile | livesweagent |
| `AGENT_PATH` | Path to integrated worker core (usually no need to change) | src/worker_core |
| `PROXY_URL` | Proxy URL for Worker subprocess | http://127.0.0.1:8045 |
| `PROXY_KEY` | Proxy key for Worker subprocess | sk-your-proxy-key |
| `VERBOSE_WORKER` | Show detailed Worker output | false |
| `MAX_WORKER_ITERATIONS` | Max Worker retries per task | 5 |
| `WORKER_TIMEOUT` | Max seconds per Worker task (0 = no timeout) | 600 |

### Runtime Configuration

All config values can be changed at runtime and are persisted to `.env`:

```bash
# Change models
/model manager claude-opus-4-6-thinking
/model worker claude-sonnet-4-20250514

# Set any config value
/config set MAX_WORKER_ITERATIONS 10
/config set VERBOSE_WORKER true

# Reload .env after external changes
/config reload

# Validate config
/config validate
```

### Worker Profiles

The `WORKER_PROFILE` setting tells GOrchestrator which configuration file to use when spawning the Worker agent. Profiles are YAML files stored in the worker core's `.miniswe/configs/` directory.

**How it works:**

When GOrchestrator runs the Worker, it executes:
```bash
uv run mini --headless --profile <WORKER_PROFILE> --model <WORKER_MODEL> --task "..."
```

The worker core loads the matching config file:
```
src/worker_core/
└── .miniswe/
    └── configs/
        ├── live.yaml             # WORKER_PROFILE=live (default, general purpose)
        ├── livesweagent.yaml     # WORKER_PROFILE=livesweagent (SWE agent)
        └── my_custom.yaml        # WORKER_PROFILE=my_custom (your own profile)
```

### Multi-Worker Setup

Workers can be managed at runtime without editing `.env`:

```bash
# Add workers with different specializations
/worker add coder claude-sonnet-4-20250514 live
/worker add tester claude-sonnet-4-20250514 livesweagent

# Activate workers
/worker set coder active
/worker set tester active

# Set per-worker API (e.g., different proxy or direct API)
/worker api tester https://api.z.ai sk-zai-key

# Worker config persists in .gorchestrator/workers.json
```

---

## Troubleshooting

### "Agent path does not exist"

```
Error: Agent path does not exist: ...
```

**Solution:** The worker core should be at `src/worker_core` by default. If you moved it, update `AGENT_PATH` in `.env`.

### "Connection refused" to proxy

```
Error: Connection refused at http://127.0.0.1:8045
```

**Solution:** Make sure your API proxy is running.

### "uv is not installed"

```
Error: uv is not installed or not in PATH
```

**Solution:** Install uv:
```bash
# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### LLM API errors

```
Error: Invalid API key
```

**Solution:**
1. Check your API keys in your proxy's configuration
2. Verify the key matches in GOrchestrator's `.env`

### Provider routing issues

If a model is misdetected, use explicit prefix: `anthropic/claude-opus-4` or `openai/gpt-4o`

### Worker timeout

```
Error: Worker task exceeded timeout (600s)
```

**Solution:** Increase the timeout:
```bash
/config set WORKER_TIMEOUT 1200
```

---

## Next Steps

Once everything is running:

1. **Read the [User Guide](user_guide.md)** to learn all available commands
2. **Check the [Architecture](architecture.md)** to understand how it all works
3. **Explore the [Developer Guide](developer_guide.md)** if you want to customize or contribute

---

<p align="center">
  <strong>Setup complete! Start chatting with your AI Software Team.</strong>
</p>

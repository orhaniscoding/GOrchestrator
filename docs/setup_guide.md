# Setup Guide: Zero to Hero

This guide will walk you through setting up the complete AI development ecosystem: **Antigravity Manager**, **Mini-SWE-GOCore**, and **GOrchestrator**.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Step 1: Antigravity Manager](#step-1-antigravity-manager)
- [Step 2: Mini-SWE-GOCore](#step-2-mini-swe-gocore)
- [Step 3: GOrchestrator](#step-3-gorchestrator)
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

## Step 1: Antigravity Manager

**Antigravity Manager** is the LiteLLM-based proxy that routes all API calls. It provides a unified interface for multiple LLM providers.

### 1.1 Clone and Install

```bash
git clone https://github.com/lbjlaq/Antigravity-Manager.git
cd Antigravity-Manager
uv sync
```

### 1.2 Configure

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```bash
# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxx

# OpenAI (optional)
OPENAI_API_KEY=sk-xxxxx

# Proxy settings
LITELLM_MASTER_KEY=sk-your-master-key
PORT=8045
```

### 1.3 Start the Proxy

```bash
uv run python -m litellm --config config.yaml --port 8045
```

### 1.4 Verify

```bash
curl http://127.0.0.1:8045/health
# Should return: {"status": "healthy"}
```

> **Keep this terminal running!** Antigravity Manager must be active for the other components to work.

---

## Step 2: Mini-SWE-GOCore

**Mini-SWE-GOCore** is the autonomous coding agent (the "Worker") that executes code and terminal commands.

### 2.1 Clone and Install

```bash
cd ..  # Go back to parent directory
git clone https://github.com/yourusername/Mini-SWE-GOCore.git
cd Mini-SWE-GOCore
uv sync
```

### 2.2 Configure

```bash
cp .env.example .env
```

Edit `.env`:

```bash
# Point to Antigravity Manager
MINI_API_BASE=http://127.0.0.1:8045
ANTHROPIC_API_KEY=sk-dummy  # Will be routed through proxy
```

### 2.3 Verify Installation

```bash
uv run mini --help
# Should show Mini-SWE-GOCore help
```

> **Note:** You don't need to run Mini-SWE manually. GOrchestrator will spawn it as needed.

---

## Step 3: GOrchestrator

**GOrchestrator** is the intelligent Manager Agent that you interact with.

### 3.1 Clone and Install

```bash
cd ..  # Go back to parent directory
git clone https://github.com/yourusername/GOrchestrator.git
cd GOrchestrator
uv sync
```

### 3.2 Configure

```bash
cp .env.example .env
```

Edit `.env` with your complete configuration:

```bash
# ============================================================
# ORCHESTRATOR (Manager Agent) Configuration
# ============================================================
ORCHESTRATOR_MODEL=claude-3-5-sonnet-20241022
ORCHESTRATOR_API_BASE=http://127.0.0.1:8045
ORCHESTRATOR_API_KEY=sk-your-master-key

# ============================================================
# WORKER (Mini-SWE-GOCore) Configuration
# ============================================================
WORKER_MODEL=claude-3-5-sonnet-20241022
WORKER_PROFILE=live
AGENT_PATH=../Mini-SWE-GOCore
PROXY_URL=http://127.0.0.1:8045
PROXY_KEY=sk-your-master-key
BYPASS_KEY=sk-dummy

# ============================================================
# Application Settings
# ============================================================
VERBOSE_WORKER=false
MAX_WORKER_ITERATIONS=5
WORKER_TIMEOUT=600
```

### 3.3 Run GOrchestrator

```bash
uv run python main.py
```

You should see:

```
┌──────────────────────────────────────────────────────────────┐
│   GOrchestrator   - Intelligent AI Agent Manager             │
└──────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      Configuration                          │
├─────────────────┬───────────────────────────────────────────┤
│ Manager Model   │ claude-3-5-sonnet-20241022                │
│ Worker Model    │ claude-3-5-sonnet-20241022                │
│ Agent Path      │ C:\...\Mini-SWE-GOCore                    │
│ Mode            │ Quiet                                     │
└─────────────────┴───────────────────────────────────────────┘

ℹ Chat with the Manager Agent. Use /help for commands.

You> _
```

---

## Configuration Deep Dive

### Understanding the Two-Agent Setup

GOrchestrator uses **two separate LLM configurations**:

```
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (Manager)                    │
│                                                             │
│  ORCHESTRATOR_MODEL     = The model YOU talk to             │
│  ORCHESTRATOR_API_BASE  = Where Manager sends LLM calls     │
│  ORCHESTRATOR_API_KEY   = Key for Manager's LLM access      │
│                                                             │
│  Role: Understand requirements, plan, delegate, explain     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ delegates to
┌─────────────────────────────────────────────────────────────┐
│                    WORKER (Mini-SWE-GOCore)                  │
│                                                             │
│  WORKER_MODEL   = The model Worker uses internally          │
│  AGENT_PATH     = Path to Mini-SWE-GOCore folder            │
│  PROXY_URL      = Where Worker sends LLM calls              │
│  PROXY_KEY      = Key for Worker's LLM access               │
│  BYPASS_KEY     = Fallback key for direct API access        │
│                                                             │
│  Role: Execute code, run commands, modify files             │
└─────────────────────────────────────────────────────────────┘
```

### Model Recommendations

| Use Case | Manager Model | Worker Model |
|----------|---------------|--------------|
| **Cost-Effective** | claude-3-haiku | claude-3-5-sonnet |
| **Balanced** | claude-3-5-sonnet | claude-3-5-sonnet |
| **Maximum Power** | claude-3-opus | claude-3-5-sonnet |

> **Tip:** The Manager handles conversation, so a faster/cheaper model works well. The Worker needs strong coding abilities.

### Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `ORCHESTRATOR_MODEL` | LLM model for Manager | claude-3-5-sonnet-20241022 |
| `ORCHESTRATOR_API_BASE` | API endpoint for Manager | http://127.0.0.1:8045 |
| `ORCHESTRATOR_API_KEY` | API key for Manager | sk-dummy-orchestrator-key |
| `WORKER_MODEL` | LLM model for Worker | claude-3-5-sonnet-20241022 |
| `WORKER_PROFILE` | Worker config profile (live, swebench, custom) | live |
| `AGENT_PATH` | Path to Mini-SWE-GOCore | ../Mini-SWE-GOCore |
| `PROXY_URL` | Proxy URL for Worker | http://127.0.0.1:8045 |
| `PROXY_KEY` | Proxy key for Worker | sk-dummy-proxy-key |
| `BYPASS_KEY` | Direct API bypass key | sk-dummy |
| `VERBOSE_WORKER` | Show detailed Worker output | false |
| `MAX_WORKER_ITERATIONS` | Max Worker retries | 5 |
| `WORKER_TIMEOUT` | Max seconds per Worker task (0 = no timeout) | 600 |

---

## Troubleshooting

### "Agent path does not exist"

```
Error: Agent path does not exist: C:\...\Mini-SWE-GOCore
```

**Solution:** Update `AGENT_PATH` in `.env` to the correct path to Mini-SWE-GOCore.

### "Connection refused" to proxy

```
Error: Connection refused at http://127.0.0.1:8045
```

**Solution:** Make sure Antigravity Manager is running:
```bash
cd Antigravity-Manager
uv run python -m litellm --config config.yaml --port 8045
```

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

### Windows encoding errors

```
UnicodeEncodeError: 'charmap' codec can't encode character
```

**Solution:** This should be automatically handled. If not, run:
```bash
set PYTHONIOENCODING=utf-8
uv run python main.py
```

### LLM API errors

```
Error: Invalid API key
```

**Solution:**
1. Check your API keys in Antigravity Manager's `.env`
2. Ensure the proxy is properly configured
3. Verify the master key matches in all `.env` files

---

## Next Steps

Once everything is running:

1. **Read the [User Guide](user_guide.md)** to learn how to interact with GOrchestrator
2. **Check the [Architecture](architecture.md)** to understand how it all works
3. **Explore the [Developer Guide](developer_guide.md)** if you want to customize or contribute

---

<p align="center">
  <strong>Setup complete! Start chatting with your AI Software Team.</strong>
</p>

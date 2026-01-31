# Architecture

This document explains the technical architecture of GOrchestrator and how its components interact.

## Table of Contents

- [System Overview](#system-overview)
- [The Manager-Worker Pattern](#the-manager-worker-pattern)
- [Component Details](#component-details)
- [Data Flow](#data-flow)
- [Session Persistence](#session-persistence)
- [Tool Calling Mechanism](#tool-calling-mechanism)

---

## System Overview

GOrchestrator implements a **Manager-Worker** architecture where an intelligent LLM-powered Manager Agent orchestrates conversations with users and delegates coding tasks to a Worker Agent.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SYSTEM ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    ┌─────────────┐                                                          │
│    │    USER     │                                                          │
│    │   (Human)   │                                                          │
│    └──────┬──────┘                                                          │
│           │ Natural Language                                                │
│           ▼                                                                 │
│    ┌─────────────────────────────────────────────────────────────────┐     │
│    │                      GORCHESTRATOR                               │     │
│    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │     │
│    │  │  Console UI │  │   Session   │  │     Manager Agent       │ │     │
│    │  │   (Rich)    │  │   Engine    │  │  (LiteLLM + Tools)      │ │     │
│    │  └─────────────┘  └─────────────┘  └───────────┬─────────────┘ │     │
│    │                                                 │               │     │
│    │                                    Tool Call: delegate_to_worker│     │
│    │                                                 │               │     │
│    │  ┌──────────────────────────────────────────────▼─────────────┐│     │
│    │  │                    Agent Worker                            ││     │
│    │  │              (Subprocess Wrapper)                          ││     │
│    │  └──────────────────────────────────────────────┬─────────────┘│     │
│    └─────────────────────────────────────────────────┼───────────────┘     │
│                                                       │                     │
│                                          subprocess.Popen                   │
│                                                       │                     │
│    ┌─────────────────────────────────────────────────▼───────────────┐     │
│    │                      MINI-SWE-GOCORE                             │     │
│    │                     (External Process)                           │     │
│    │                                                                  │     │
│    │   - Autonomous Coding Agent                                      │     │
│    │   - File System Access                                           │     │
│    │   - Terminal Command Execution                                   │     │
│    │   - Code Generation & Modification                               │     │
│    └─────────────────────────────────────────────────┬───────────────┘     │
│                                                       │                     │
│                                                       ▼                     │
│    ┌──────────────────────────────────────────────────────────────────┐    │
│    │                        FILE SYSTEM                                │    │
│    │                   (User's Project Files)                          │    │
│    └──────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## The Manager-Worker Pattern

### Why This Pattern?

Traditional AI coding assistants directly execute code when you ask. GOrchestrator uses a **two-tier architecture** for better results:

| Layer | Role | Benefit |
|-------|------|---------|
| **Manager** | Understands, plans, reviews | Better requirement analysis, context retention |
| **Worker** | Executes, codes, runs commands | Focused execution, specialized for coding |

### Separation of Concerns

```
┌─────────────────────────────────────────────────────────────┐
│                    MANAGER AGENT (🧠)                        │
├─────────────────────────────────────────────────────────────┤
│ Responsibilities:                                           │
│ ✓ Understand user requirements                              │
│ ✓ Ask clarifying questions                                  │
│ ✓ Decide when to delegate vs. respond directly              │
│ ✓ Formulate clear task descriptions for Worker              │
│ ✓ Review and explain Worker output                          │
│ ✓ Maintain conversation context                             │
│                                                             │
│ Does NOT:                                                   │
│ ✗ Write code directly                                       │
│ ✗ Execute terminal commands                                 │
│ ✗ Modify files                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ delegates
┌─────────────────────────────────────────────────────────────┐
│                    WORKER AGENT (👷)                         │
├─────────────────────────────────────────────────────────────┤
│ Responsibilities:                                           │
│ ✓ Write and modify code                                     │
│ ✓ Execute terminal commands                                 │
│ ✓ Create and delete files                                   │
│ ✓ Run tests                                                 │
│ ✓ Report results                                            │
│                                                             │
│ Does NOT:                                                   │
│ ✗ Communicate with user directly                            │
│ ✗ Make architectural decisions                              │
│ ✗ Maintain conversation history                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Session Engine (`src/core/engine.py`)

The Session Engine is the main orchestrator that manages the interaction loop.

```python
class SessionEngine:
    """Orchestrates User <-> Manager <-> Worker interactions."""

    def start_interactive_mode(self):
        """Main loop: get input -> process -> display"""
        while running:
            user_input = ui.get_user_input()

            if is_slash_command(user_input):
                handle_slash_command(user_input)
            else:
                response = manager.chat(user_input)
                display_response(response)
```

**Responsibilities:**
- Initialize and manage the Manager Agent
- Handle slash commands (`/save`, `/load`, etc.)
- Route user input to appropriate handlers
- Manage session persistence
- Coordinate UI updates

### 2. Manager Agent (`src/core/manager.py`)

The Manager Agent is an LLM-powered conversational agent with tool-calling capabilities.

```python
class ManagerAgent:
    """LLM-powered agent that communicates with users."""

    def __init__(self):
        self.messages = [system_prompt]
        self.worker = AgentWorker()

    def chat(self, user_message: str) -> ManagerResponse:
        """Process user message, possibly calling tools."""
        self.messages.append(user_message)

        response = litellm.completion(
            messages=self.messages,
            tools=[WORKER_TOOL],
        )

        if response.has_tool_calls:
            results = self.execute_tools(response.tool_calls)
            # Continue conversation with tool results

        return response
```

**Key Features:**
- Uses LiteLLM for LLM API calls
- Maintains conversation history
- Defines and executes tools
- Streams Worker output via callbacks

### 3. Agent Worker (`src/core/worker.py`)

The Worker wraps the Mini-SWE-GOCore subprocess.

```python
class AgentWorker:
    """Subprocess wrapper for Mini-SWE-GOCore."""

    def run_task(self, task: str, on_output: Callable) -> TaskResult:
        """Run a task and stream output."""
        process = subprocess.Popen(
            ["uv", "run", "mini", "--headless", "--task", task],
            cwd=agent_path,
            env=agent_env,
            stdout=subprocess.PIPE,
        )

        for line in process.stdout:
            on_output(line)  # Stream to UI

        return TaskResult(...)
```

**Key Features:**
- Spawns Mini-SWE-GOCore as subprocess
- Injects environment variables for API access
- Streams output in real-time
- Returns structured TaskResult

### 4. Console UI (`src/ui/console.py`)

Rich-based terminal interface with role-specific formatting.

```python
class ConsoleUI:
    """Rich terminal interface."""

    def display_user_message(self, msg):     # 👤 Green panel
    def display_manager_message(self, msg):  # 🧠 Cyan panel
    def display_worker_step(self, entry):    # 👷 Dim text
    def display_worker_result(self, result): # Result panel
```

---

## Data Flow

### Complete Request Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           REQUEST FLOW                                    │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. USER INPUT                                                           │
│     "Create a Flask app"                                                 │
│           │                                                              │
│           ▼                                                              │
│  2. SESSION ENGINE                                                       │
│     - Validates input                                                    │
│     - Routes to Manager                                                  │
│           │                                                              │
│           ▼                                                              │
│  3. MANAGER AGENT                                                        │
│     - Adds to conversation history                                       │
│     - Calls LLM with tools                                               │
│           │                                                              │
│           ▼                                                              │
│  4. LLM DECISION                                                         │
│     ┌─────────────────────────────────────────────┐                     │
│     │ Response includes tool_call:                 │                     │
│     │ delegate_to_worker("Create Flask app...")   │                     │
│     └─────────────────────────────────────────────┘                     │
│           │                                                              │
│           ▼                                                              │
│  5. TOOL EXECUTION                                                       │
│     - Manager calls AgentWorker.run_task()                               │
│     - Worker spawns Mini-SWE-GOCore                                      │
│           │                                                              │
│           ▼                                                              │
│  6. WORKER EXECUTION                                                     │
│     - Mini-SWE creates files                                             │
│     - Streams output back                                                │
│     - Returns TaskResult                                                 │
│           │                                                              │
│           ▼                                                              │
│  7. RESULT INTEGRATION                                                   │
│     - Tool result added to Manager context                               │
│     - Manager formulates final response                                  │
│           │                                                              │
│           ▼                                                              │
│  8. USER RESPONSE                                                        │
│     "Done! I've created app.py with..."                                  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Message Flow Diagram

```
User          SessionEngine      ManagerAgent       AgentWorker      Mini-SWE
  │                 │                  │                 │               │
  │ "Create app"    │                  │                 │               │
  │────────────────►│                  │                 │               │
  │                 │  chat(msg)       │                 │               │
  │                 │─────────────────►│                 │               │
  │                 │                  │ LLM call        │               │
  │                 │                  │═══════════╗     │               │
  │                 │                  │           ║     │               │
  │                 │                  │◄══════════╝     │               │
  │                 │                  │ tool_call       │               │
  │                 │                  │ detected        │               │
  │                 │                  │                 │               │
  │                 │                  │  run_task()     │               │
  │                 │                  │────────────────►│               │
  │                 │                  │                 │ subprocess    │
  │                 │                  │                 │──────────────►│
  │                 │                  │                 │               │
  │                 │                  │                 │  streaming    │
  │                 │                  │  on_output()    │◄─────────────┤│
  │                 │  UI update       │◄────────────────│               │
  │ [Worker Step]   │◄─────────────────│                 │               │
  │                 │                  │                 │               │
  │                 │                  │                 │  TaskResult   │
  │                 │                  │◄────────────────│◄──────────────│
  │                 │                  │                 │               │
  │                 │                  │ LLM call        │               │
  │                 │                  │ (with result)   │               │
  │                 │                  │═══════════╗     │               │
  │                 │                  │◄══════════╝     │               │
  │                 │  ManagerResponse │                 │               │
  │                 │◄─────────────────│                 │               │
  │ [Manager msg]   │                  │                 │               │
  │◄────────────────│                  │                 │               │
  │                 │                  │                 │               │
```

---

## Session Persistence

### How Sessions Are Saved

GOrchestrator automatically saves conversation state to enable context continuity.

```
.gorchestrator/
└── sessions/
    ├── latest_session.json    # Auto-saved after each turn
    ├── manual_save.json       # User-created snapshots
    └── my_project.json        # Named sessions
```

### Session File Structure

```json
{
  "version": "2.0",
  "saved_at": "2024-01-15T10:30:00.000000",
  "mode": "auto",
  "manager_history": [
    {
      "role": "system",
      "content": "You are GOrchestrator...",
      "timestamp": "2024-01-15T10:00:00.000000"
    },
    {
      "role": "user",
      "content": "Create a Flask app",
      "timestamp": "2024-01-15T10:01:00.000000"
    },
    {
      "role": "assistant",
      "content": "I'll create a Flask application...",
      "timestamp": "2024-01-15T10:01:05.000000",
      "tool_calls": [...]
    },
    {
      "role": "tool",
      "content": "Worker Result: SUCCESS...",
      "tool_call_id": "call_abc123",
      "name": "delegate_to_worker"
    }
  ]
}
```

### Session Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                    SESSION LIFECYCLE                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. START                                                   │
│     └─► Try load("latest_session")                          │
│         └─► If exists: restore history                      │
│         └─► If not: start fresh                             │
│                                                             │
│  2. EACH TURN                                               │
│     └─► User sends message                                  │
│     └─► Manager responds                                    │
│     └─► Auto-save to latest_session.json                    │
│                                                             │
│  3. MANUAL SAVE                                             │
│     └─► /save my_project                                    │
│     └─► Creates my_project.json                             │
│                                                             │
│  4. LOAD                                                    │
│     └─► /load my_project                                    │
│     └─► Restores full conversation history                  │
│     └─► Manager has context of previous work                │
│                                                             │
│  5. EXIT                                                    │
│     └─► Final auto-save                                     │
│     └─► Session persisted for next run                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Tool Calling Mechanism

### Tool Definition

The Manager Agent has one primary tool: `delegate_to_worker`

```python
WORKER_TOOL = {
    "type": "function",
    "function": {
        "name": "delegate_to_worker",
        "description": "Delegate a coding task to the Worker Agent...",
        "parameters": {
            "type": "object",
            "properties": {
                "task_description": {
                    "type": "string",
                    "description": "Detailed task description..."
                },
                "context": {
                    "type": "string",
                    "description": "Additional context..."
                }
            },
            "required": ["task_description"]
        }
    }
}
```

### Tool Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    TOOL CALLING FLOW                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. LLM returns response with tool_calls                    │
│     {                                                       │
│       "tool_calls": [{                                      │
│         "id": "call_abc123",                                │
│         "function": {                                       │
│           "name": "delegate_to_worker",                     │
│           "arguments": "{\"task_description\": \"...\"}"    │
│         }                                                   │
│       }]                                                    │
│     }                                                       │
│                                                             │
│  2. Manager parses tool calls                               │
│     - Extracts function name and arguments                  │
│     - Calls _execute_worker_task()                          │
│                                                             │
│  3. Worker executes task                                    │
│     - Spawns subprocess                                     │
│     - Streams output                                        │
│     - Returns TaskResult                                    │
│                                                             │
│  4. Tool result added to messages                           │
│     {                                                       │
│       "role": "tool",                                       │
│       "tool_call_id": "call_abc123",                        │
│       "content": "Worker Result: SUCCESS..."                │
│     }                                                       │
│                                                             │
│  5. LLM called again with tool result                       │
│     - Generates final user-facing response                  │
│     - Explains what Worker did                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Environment Variable Injection

When the Worker spawns Mini-SWE-GOCore, it injects environment variables:

```python
def get_agent_env(self) -> dict[str, str]:
    return {
        "MINI_API_BASE": self.PROXY_URL,      # API endpoint
        "ANTHROPIC_API_KEY": self.BYPASS_KEY,  # For Anthropic models
        "OPENAI_API_KEY": self.BYPASS_KEY,     # For OpenAI models
        "LITELLM_API_KEY": self.PROXY_KEY,     # For proxy auth
    }
```

This ensures the Worker process can communicate with Antigravity Manager without separate configuration.

---

<p align="center">
  <strong>Understanding the architecture helps you debug issues and extend functionality.</strong>
</p>

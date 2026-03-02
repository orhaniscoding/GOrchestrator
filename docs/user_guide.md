# User Guide

Learn how to effectively use GOrchestrator to manage your coding projects through natural conversation.

## Table of Contents

- [Understanding the Interface](#understanding-the-interface)
- [The Dashboard](#the-dashboard)
- [Chatting with the Manager](#chatting-with-the-manager)
- [Input Controls](#input-controls)
- [Slash Commands](#slash-commands)
- [Multi-Worker Usage](#multi-worker-usage)
- [Runtime Configuration](#runtime-configuration)
- [Session Management](#session-management)
- [Safety Features](#safety-features)
- [Workflow Examples](#workflow-examples)
- [Tips and Best Practices](#tips-and-best-practices)

---

## Understanding the Interface

GOrchestrator uses a role-based interface with distinct participants:

### The Participants

| Icon | Role | Description |
|------|------|-------------|
| **You** | User | Your messages appear in green |
| **Manager** | Architect Agent | Cyan panels, understands and plans |
| **[worker_name]** | Coding Agent(s) | Dim/grey output with name prefix, executes tasks |

### Visual Example

```
┌──────────────────────────────────────────────────────────────┐
│ You                                                          │
│ Create a Flask app with a /hello endpoint                    │
└──────────────────────────────────────────────────────────────┘

  Analyzing your request...

┌──────────────────────────────────────────────────────────────┐
│ Manager                                                      │
│ I'll create a Flask application with a /hello endpoint.      │
│ Let me delegate this to the Worker...                        │
└──────────────────────────────────────────────────────────────┘

  Calling tool: delegate_to_coder

─────────────────── Worker Execution ──────────────────────────
    [coder] Step 1...
    [coder] Step 2...
    [coder] Step 3...
┌──────────────────────────────────────────────────────────────┐
│ Worker Result [coder]                                        │
│ SUCCESS  |  Steps: 3  |  Cost: $0.0234  |  Time: 12.3s      │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ Manager                                                      │
│ Done! I've created `app.py` with:                            │
│ - Flask app initialization                                   │
│ - `/hello` endpoint that returns "Hello, World!"             │
│                                                              │
│ Run with: `flask run` or `python app.py`                     │
└──────────────────────────────────────────────────────────────┘
```

---

## The Dashboard

On startup, GOrchestrator displays a rich dashboard showing the current state:

```
┌────────────────────── GOrchestrator ──────────────────────┐
│  Session: bold-phoenix (new)                              │
│  Manager: claude-sonnet-4-20250514 @ http://127.0.0.1:8045│
│                                                           │
│  Workers:                                                 │
│    ● default  (claude-sonnet-4-20250514, live) [primary]  │
│    ● tester   (claude-sonnet-4-20250514, livesweagent)    │
│    ○ docs     (gpt-4o, live)                              │
│                                                           │
│  Mode: Quiet | Confirm: OFF                               │
└───────────────────────────────────────────────────────────┘
```

- **Session**: Current session name and status (new/restored)
- **Manager**: Model and API endpoint
- **Workers**: All registered workers with status
  - `●` = active, `○` = inactive
  - `[primary]` = settings synced to `.env`
  - `@ url` = per-worker API endpoint (if set)
- **Mode**: Quiet (summary) or Verbose (detailed output)
- **Confirm**: Whether tasks require user approval before execution

---

## Chatting with the Manager

The Manager Agent understands natural language:

### Conversational Requests (No Worker Needed)

```
You> What's the best way to structure a Python project?

Manager: For a Python project, I recommend this structure:
   - src/ for source code
   - tests/ for test files
   - docs/ for documentation
   ...
```

### Task Requests (Worker Will Be Used)

```
You> Create a REST API with user authentication

Manager: I'll create a REST API with JWT authentication...
   Calling tool: delegate_to_coder
   ...
```

### Follow-up Questions

```
You> What files did the Worker create?

Manager: The Worker created the following files:
   - app.py (main application)
   - models/user.py (User model)
   - routes/auth.py (authentication routes)
```

### Requesting Changes

```
You> Add input validation to the login endpoint

Manager: I'll add input validation using Pydantic...
```

---

## Input Controls

| Key | Action |
|-----|--------|
| **Tab** | Autocomplete slash commands and sub-commands |
| **Arrow Up/Down** | Browse input history |
| **Ctrl+J** | Insert new line (multi-line input) |
| **Multi-line paste** | Paste multi-line text directly |

### Multi-line Input Example

Press **Ctrl+J** to insert new lines within your input:

```
You> Here is the error I'm seeing:    [Ctrl+J]
     TypeError: 'NoneType' object is not iterable    [Ctrl+J]
     on line 42 of app.py. Please fix it.
```

### Tab Autocomplete

Type `/` and press **Tab** to see all available commands. Type `/worker ` and press **Tab** to see sub-commands like `list`, `add`, `remove`, etc.

---

## Slash Commands

### Session Commands

| Command | Alias | Description |
|---------|-------|-------------|
| `/save [name]` | `/s` | Save current session |
| `/load [id or name]` | | Load session by ID or name (shows list if no arg) |
| `/list` | `/l` | List all saved sessions |
| `/new [name]` | | Start a new session (random name if omitted) |
| `/clear` | | Clear conversation and start new session |
| `/clearterminal` | `/ct` | Clear terminal screen only |
| `/history` | | Show full conversation history |

### Display Commands

| Command | Description |
|---------|-------------|
| `/verbose` | Show detailed Worker output (every step) |
| `/quiet` | Show summarized Worker output (default) |

### Config Commands

| Command | Description |
|---------|-------------|
| `/model [manager\|worker] <name>` | Change model (saved to .env) |
| `/config show` | Show current configuration table |
| `/config reload` | Reload .env file |
| `/config validate` | Check config for issues |
| `/config set <KEY> <VALUE>` | Set a config value (saved to .env) |

**Config aliases:**
- `/config set manager <model>` sets `ORCHESTRATOR_MODEL`
- `/config set worker <model>` sets `WORKER_MODEL`

### Worker Management

| Command | Alias | Description |
|---------|-------|-------------|
| `/worker list` | `/w list` | List all worker profiles |
| `/worker add <name> [model] [profile]` | | Add a new worker |
| `/worker remove <name>` | | Remove a worker |
| `/worker set <name> active` | | Activate a worker |
| `/worker set <name> inactive` | | Deactivate a worker |
| `/worker set <name> primary` | | Set as primary worker (.env sync) |
| `/worker show <name>` | | Show worker details (model, profile, API, tool) |
| `/worker model <name> <model>` | | Change a worker's model |
| `/worker profile <name> <profile>` | | Change a worker's profile |
| `/worker api <name> <url> [key]` | | Set per-worker API endpoint |

### Sub-Manager Management (Mixture of Agents)

Sub-Managers are expert advisor AI agents that the Manager consults before making decisions.

| Command | Alias | Description |
|---------|-------|-------------|
| `/submanager list` | `/sm list` | List all sub-managers |
| `/submanager add <name> <profile> [model]` | | Add a new sub-manager advisor |
| `/submanager remove <name>` | | Remove a sub-manager |
| `/submanager set <name> active\|inactive` | | Activate/deactivate a sub-manager |
| `/submanager show <name>` | | Show sub-manager details |
| `/submanager model <name> <model>` | | Change sub-manager's model |
| `/submanager profile <name> <profile>` | | Change sub-manager's profile |
| `/submanager api <name> <base> [key]` | | Set sub-manager's API endpoint |
| `/submanager description <name> <text>` | | Set sub-manager's description |
| `/submanager llm <name> list` | | List parallel LLMs for a sub-manager |
| `/submanager llm <name> add <llm> <model>` | | Add a parallel LLM to sub-manager |
| `/submanager llm <name> remove <llm>` | | Remove a parallel LLM |

### Team Management

Teams are saved Manager + Sub-Manager combinations that can be activated in one step.

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

### Manager LLM Pool

Run multiple LLMs in parallel for the Manager and synthesize the best answer.

| Command | Description |
|---------|-------------|
| `/manager llm list` | List parallel LLMs for the Manager |
| `/manager llm add <name> <model> [api_base] [api_key]` | Add a parallel LLM |
| `/manager llm remove <name>` | Remove a parallel LLM |

### Safety Commands

| Command | Description |
|---------|-------------|
| `/confirm on\|off` | Ask before Worker executes |
| `/undo` | Revert last Worker changes (git checkpoint) |
| `/checkpoints` | List available git checkpoints |

### Other

| Command | Alias | Description |
|---------|-------|-------------|
| `/help` | `/h` | Show help information |
| `exit` | `q` | Exit the application |

---

## Multi-Worker Usage

GOrchestrator supports multiple Worker agents that can execute tasks in parallel.

### Adding and Managing Workers

```bash
# Add workers with different specializations
You> /worker add coder claude-sonnet-4-20250514 live
You> /worker add tester claude-sonnet-4-20250514 livesweagent

# Activate workers (multiple can be active)
You> /worker set coder active
You> /worker set tester active

# Set one as primary (its settings sync to .env)
You> /worker set coder primary

# View worker details
You> /worker show coder

# Set per-worker API endpoint (e.g., different proxy)
You> /worker api tester https://api.z.ai sk-zai-key

# List all workers
You> /worker list
```

### How Parallel Execution Works

When multiple workers are active, the Manager gets a `delegate_to_<name>` tool for each one. The Manager decides which worker(s) to use based on the task:

```
You> Create app.py and write comprehensive tests for it

Manager: I'll delegate coding to 'coder' and testing to 'tester'
  in parallel...

  [coder]  Step 1... Step 2... Step 3...
  [tester] Step 1... Step 2...

  Worker Result [coder]:  SUCCESS | Steps: 3 | $0.02
  Worker Result [tester]: SUCCESS | Steps: 2 | $0.01

Manager: Done! Created app.py with 4 endpoints and
test_app.py with 12 test cases.
```

### Worker Profiles

The profile controls the Worker's behavior (system prompts, model settings, limits):

| Profile | Best For |
|---------|----------|
| `live` | General purpose tasks, quick edits |
| `livesweagent` | Complex software engineering, debugging, refactoring |

Profiles are YAML files in `src/worker_core/.miniswe/configs/`. Create custom profiles by copying and modifying existing ones.

---

## Runtime Configuration

All configuration changes made at runtime are persisted to `.env`:

### Changing Models

```bash
# Change Manager model
You> /model manager claude-opus-4-6-thinking

# Change default Worker model
You> /model worker claude-sonnet-4-20250514

# Change a specific worker's model
You> /worker model tester gpt-4o
```

### Viewing and Setting Config

```bash
# View current configuration
You> /config show

# Set any config value
You> /config set MAX_WORKER_ITERATIONS 10
You> /config set VERBOSE_WORKER true
You> /config set WORKER_TIMEOUT 1200

# Reload .env file after external changes
You> /config reload

# Check for config issues
You> /config validate
```

---

## Session Management

### Session Names

Sessions get random names like `bold-phoenix`, `swift-nebula`, etc. You can also provide custom names:

```bash
# Start a new session with random name
You> /new

# Start a new session with custom name
You> /new my-flask-project

# Save current session
You> /save

# Save with specific name
You> /save before-refactor
```

### Loading Sessions

```bash
# Show available sessions
You> /list

# Load by name
You> /load my-flask-project

# Load with no argument shows session list
You> /load
```

### Auto-Save

Sessions are automatically saved:
- After each conversation turn
- On `exit` / `quit`
- On Ctrl+C or EOFError
- Via `atexit` handler

### Auto-Resume

On startup, GOrchestrator automatically tries to resume the latest session. The dashboard shows `(restored, N messages)` when a session is resumed.

---

## Safety Features

### Confirmation Mode

Enable confirmation to review tasks before Worker execution:

```bash
You> /confirm on
# Now every Worker task will ask for your approval first

You> Create a new file

Manager: I'll create the file...
  Task: "Create new_file.py with hello world"
  Execute this task? [y/N]: y
  [default] Step 1...

You> /confirm off
# Back to automatic execution
```

### Git Checkpoints and Undo

GOrchestrator creates git checkpoints before each Worker task:

```bash
# View available checkpoints
You> /checkpoints

# Undo last Worker changes
You> /undo
```

---

## Workflow Examples

### Example 1: Multi-Worker Parallel Development

```
You> /worker add backend claude-sonnet-4-20250514 live
You> /worker add frontend claude-sonnet-4-20250514 live
You> /worker set backend active
You> /worker set frontend active

You> Create a REST API backend and a React frontend for a todo app

Manager: I'll delegate the backend to 'backend' and frontend
  to 'frontend' in parallel...

  [backend] Creating Flask API...
  [frontend] Creating React app...

Manager: Done! Backend API runs on :5000, frontend on :3000.
```

### Example 2: Debugging with Verbose Mode

```
You> /verbose
You> There's a bug in app.py - the /users endpoint returns 500

  [default] Step 1: Reading app.py...
  [default] Step 2: Found issue on line 45 - NoneType access
  [default] Step 3: Applying fix...
  [default] Step 4: Running tests...
  [default] Step 5: All tests pass

Manager: Fixed! The issue was a missing null check on line 45.
```

### Example 3: Per-Worker API Endpoints

```
# Use different API endpoints for different workers
You> /worker api backend https://api.anthropic.com sk-ant-xxx
You> /worker api frontend https://api.openai.com sk-oai-xxx

# Now each worker routes through its own API
You> Build the full-stack app
```

### Example 4: Incremental Development

```
You> Create a basic Flask app
... [Worker completes]

You> Add a User model with SQLAlchemy
... [Worker completes]

You> /save after-models

You> Add authentication endpoints
... [Worker completes]

# Something went wrong?
You> /undo
# Or load previous checkpoint
You> /load after-models
```

### Example 5: Using Sub-Managers for Expert Advice

```
# Add sub-managers with different specializations
You> /submanager add architect architect claude-sonnet-4-20250514
You> /submanager add security security claude-sonnet-4-20250514

# Activate them
You> /submanager set architect active
You> /submanager set security active

# Now the Manager will consult these advisors before delegating
You> Refactor the authentication system

Manager: Let me consult my advisors first...
  [architect] Recommends separating auth into its own module...
  [security] Suggests using bcrypt for password hashing...
Manager: Based on expert advice, I'll delegate the refactoring...
```

### Example 6: Using Teams

```
# Create a team with a manager profile and sub-managers
You> /team add review-team code-review architect,security

# Activate the team (sets profile + activates sub-managers)
You> /team activate review-team

# Now the Manager uses "code-review" profile and consults
# architect + security sub-managers automatically

# Deactivate team when done
You> /team deactivate
```

### Example 7: Manager Parallel LLM Pool

```
# Add parallel LLMs to the Manager
You> /manager llm add gpt4o gpt-4o https://api.openai.com/v1 sk-xxx
You> /manager llm add gemini gemini-2.0-flash

# Now the Manager queries multiple LLMs in parallel
# and synthesizes the best answer
You> /manager llm list

# Remove a parallel LLM
You> /manager llm remove gemini
```

### Example 8: Sub-Manager with Parallel LLMs

```
# Add parallel LLMs to a sub-manager
You> /submanager llm architect add gpt4o gpt-4o
You> /submanager llm architect add gemini gemini-2.0-flash

# The architect sub-manager will now run its analysis
# through multiple LLMs and synthesize results
You> /submanager llm architect list
```

---

## Tips and Best Practices

### 1. Be Specific

- **Vague:** "Make it better"
- **Specific:** "Add input validation to the /register endpoint"

### 2. Provide Context

- **No context:** "Fix the error"
- **With context:** "Fix the TypeError on line 42 of app.py"

### 3. Use Incremental Requests

Break large tasks into smaller, manageable pieces.

### 4. Ask for Explanations

After the Worker completes a task:

```
You> Explain what changes were made
You> What's the best way to test this?
You> Are there any security concerns?
```

### 5. Save Before Risky Changes

```
You> /save before_refactor
You> Refactor the entire database layer
# If something goes wrong: /undo or /load before_refactor
```

### 6. Use Verbose Mode for Debugging

```
You> /verbose
You> Fix the failing test
# See detailed Worker output to understand what's happening
You> /quiet
# Back to summary mode
```

### 7. Specialize Workers

Create workers with different profiles for different tasks:

```
You> /worker add coder claude-sonnet-4-20250514 live
You> /worker add reviewer claude-opus-4-6-thinking livesweagent
```

### 8. Use Config Aliases

Quick model changes:

```
You> /config set manager claude-opus-4-6-thinking
You> /config set worker claude-sonnet-4-20250514
```

---

<p align="center">
  <strong>Now you're ready to work with your AI Software Team!</strong>
</p>

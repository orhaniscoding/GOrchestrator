# User Guide

Learn how to effectively use GOrchestrator to manage your coding projects through natural conversation.

## Table of Contents

- [Understanding the Interface](#understanding-the-interface)
- [Chatting with the Manager](#chatting-with-the-manager)
- [Slash Commands](#slash-commands)
- [Workflow Examples](#workflow-examples)
- [Tips and Best Practices](#tips-and-best-practices)

---

## Understanding the Interface

GOrchestrator uses a role-based interface with three distinct participants:

### The Participants

| Icon | Role | Description |
|------|------|-------------|
| 👤 **You** | User | Your messages appear in green |
| 🧠 **Manager** | Architect Agent | Cyan panels, understands and plans |
| 👷 **Worker** | Coding Agent | Dim/grey output, executes tasks |

### Visual Example

```
┌──────────────────────────────────────────────────────────────┐
│ 👤 You                                                       │
│ Create a Flask app with a /hello endpoint                    │
└──────────────────────────────────────────────────────────────┘

  🧠 Analyzing your request...

┌──────────────────────────────────────────────────────────────┐
│ 🧠 Manager                                                   │
│ I'll create a Flask application with a /hello endpoint.      │
│ Let me delegate this to the Worker...                        │
└──────────────────────────────────────────────────────────────┘

  🔧 Calling tool: delegate_to_worker

─────────────────── 👷 Worker Execution ───────────────────────
    Step 1...
    Step 2...
    Step 3...
┌──────────────────────────────────────────────────────────────┐
│ 👷 Worker Result                                             │
│ ✓ SUCCESS  |  Steps: 3  |  Cost: $0.0234  |  Time: 12.3s    │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ 🧠 Manager                                                   │
│ Done! I've created `app.py` with:                            │
│ - Flask app initialization                                   │
│ - `/hello` endpoint that returns "Hello, World!"             │
│                                                              │
│ Run with: `flask run` or `python app.py`                     │
└──────────────────────────────────────────────────────────────┘
```

---

## Chatting with the Manager

The Manager Agent understands natural language. Here's how to communicate effectively:

### Conversational Requests (No Worker Needed)

For questions and discussions, the Manager responds directly:

```
You> What's the best way to structure a Python project?

🧠 Manager: For a Python project, I recommend this structure:
   - src/ for source code
   - tests/ for test files
   - docs/ for documentation
   ...
```

```
You> Explain what dependency injection is

🧠 Manager: Dependency injection is a design pattern where...
```

### Task Requests (Worker Will Be Used)

For coding tasks, the Manager delegates to the Worker:

```
You> Create a REST API with user authentication

🧠 Manager: I'll create a REST API with JWT authentication...
   🔧 Calling tool: delegate_to_worker
   ...
```

### Follow-up Questions

You can ask about what just happened:

```
You> What files did the Worker create?

🧠 Manager: The Worker created the following files:
   - app.py (main application)
   - models/user.py (User model)
   - routes/auth.py (authentication routes)
```

### Requesting Changes

Ask for modifications naturally:

```
You> Add input validation to the login endpoint

🧠 Manager: I'll add input validation using Pydantic...
```

---

## Slash Commands

GOrchestrator supports several slash commands for session management:

### Session Management

| Command | Description | Example |
|---------|-------------|---------|
| `/save [name]` | Save current session | `/save my_project` |
| `/load [name]` | Load a saved session | `/load my_project` |
| `/list` | List all saved sessions | `/list` |
| `/clear` | Clear conversation history and screen | `/clear` |

**Session Persistence:**
- Sessions are automatically saved after each turn
- Use `/save` to create named snapshots
- Context is preserved across sessions

```
You> /save flask_api_project
✓ Session saved to: .gorchestrator/sessions/flask_api_project.json

You> /list
ℹ Available sessions:
  - flask_api_project
  - latest_session
  - manual_save

You> /load flask_api_project
✓ Session 'flask_api_project' loaded
ℹ Previous conversation context restored.
```

### Display Settings

| Command | Description |
|---------|-------------|
| `/verbose` | Show detailed Worker output |
| `/quiet` | Show summarized Worker output (default) |

**Verbose Mode:**
```
You> /verbose
✓ Verbose mode enabled. Worker output will be shown in detail.

# Now Worker output shows every step:
    [Step 1] Reading file structure...
    [Step 2] Creating app.py...
    [Step 3] Writing Flask boilerplate...
    💰 Cost: $0.0234
```

**Quiet Mode:**
```
You> /quiet
✓ Quiet mode enabled. Worker output will be summarized.

# Worker output is minimal:
    Step 3...
┌──────────────────────────────────────────────────────────────┐
│ 👷 Worker Result                                             │
│ ✓ SUCCESS  |  Steps: 3  |  Cost: $0.0234                    │
└──────────────────────────────────────────────────────────────┘
```

### Other Commands

| Command | Description |
|---------|-------------|
| `/history` | Show conversation history |
| `/help` | Show help information |
| `exit` or `quit` | Exit the application |

---

## Workflow Examples

### Example 1: Creating a Flask Application

**Goal:** Create a complete Flask web application with database

```
You> Create a Flask app with SQLite database for a todo list

🧠 Manager: I'll create a Flask application with:
- SQLite database using SQLAlchemy
- Todo model with title, description, completed status
- CRUD endpoints for todos
- Basic error handling

Let me delegate this to the Worker...

   🔧 Calling tool: delegate_to_worker
   ─────────────────── 👷 Worker Execution ───────────────────
       Step 1...
       Step 2...
       Step 3...
   ┌──────────────────────────────────────────────────────────┐
   │ 👷 Worker Result: ✓ SUCCESS | Steps: 8 | $0.0456        │
   └──────────────────────────────────────────────────────────┘

🧠 Manager: Done! I've created the following files:

**app.py** - Main application with routes:
- GET /todos - List all todos
- POST /todos - Create a todo
- PUT /todos/<id> - Update a todo
- DELETE /todos/<id> - Delete a todo

**models.py** - SQLAlchemy models
**requirements.txt** - Dependencies

To run:
```bash
pip install -r requirements.txt
python app.py
```

You> Add authentication to this app

🧠 Manager: I'll add JWT-based authentication...
```

### Example 2: Debugging Code

**Goal:** Fix a bug in existing code

```
You> There's a bug in app.py - the /users endpoint returns 500 error

🧠 Manager: I'll investigate the /users endpoint. Let me have the
Worker analyze the code and fix the issue...

   🔧 Calling tool: delegate_to_worker
   ─────────────────── 👷 Worker Execution ───────────────────
       [Analyzing app.py...]
       [Found issue: missing null check on line 45]
       [Applying fix...]
   ┌──────────────────────────────────────────────────────────┐
   │ 👷 Worker Result: ✓ SUCCESS | Steps: 5 | $0.0312        │
   └──────────────────────────────────────────────────────────┘

🧠 Manager: Found and fixed the bug!

**Issue:** The `/users` endpoint was trying to access `.name` on
a potentially None user object.

**Fix:** Added a null check before accessing user properties:
```python
if user is None:
    return jsonify({"error": "User not found"}), 404
```

The endpoint should now return proper 404 errors instead of 500.
```

### Example 3: Code Explanation (No Worker)

**Goal:** Understand existing code

```
You> Explain what this decorator does:
@app.before_request
def check_auth():
    if 'user_id' not in session:
        return redirect('/login')

🧠 Manager: This is a Flask "before request" decorator that runs
before every request to your application.

**What it does:**
1. Checks if 'user_id' exists in the session
2. If not (user not logged in), redirects to /login
3. If yes, the request continues normally

**Use case:** This is a simple authentication guard that protects
all routes. Any unauthenticated request gets redirected to login.

**Note:** This affects ALL routes. If you have public routes (like
the login page itself), you'll need to add exceptions.

Would you like me to modify this to exclude certain routes?
```

### Example 4: Project Analysis

**Goal:** Understand a codebase

```
You> Analyze the project structure and tell me what this app does

🧠 Manager: I'll have the Worker scan the project structure...

   🔧 Calling tool: delegate_to_worker
   ─────────────────── 👷 Worker Execution ───────────────────
       [Scanning directory structure...]
       [Reading key files...]
   ┌──────────────────────────────────────────────────────────┐
   │ 👷 Worker Result: ✓ SUCCESS | Steps: 4 | $0.0189        │
   └──────────────────────────────────────────────────────────┘

🧠 Manager: Based on my analysis, this is a **Flask-based REST API**
for a task management system.

**Project Structure:**
```
├── app.py          # Main entry point
├── models/         # SQLAlchemy models
│   ├── user.py     # User model
│   └── task.py     # Task model
├── routes/         # API endpoints
│   ├── auth.py     # Login/register
│   └── tasks.py    # CRUD for tasks
└── utils/          # Helpers
    └── auth.py     # JWT utilities
```

**Key Features:**
- User authentication with JWT
- Task CRUD operations
- User-task relationship (users own tasks)

Would you like me to explain any specific part in more detail?
```

---

## Tips and Best Practices

### 1. Be Specific

❌ **Vague:** "Make it better"
✅ **Specific:** "Add input validation to the /register endpoint"

### 2. Provide Context

❌ **No context:** "Fix the error"
✅ **With context:** "Fix the TypeError on line 42 of app.py"

### 3. Use Incremental Requests

Instead of one massive request, break it down:

```
You> Create a basic Flask app
... [Worker completes]

You> Add a User model with SQLAlchemy
... [Worker completes]

You> Add authentication endpoints
... [Worker completes]
```

### 4. Ask for Explanations

After the Worker completes a task:

```
You> Explain what changes were made
You> What's the best way to test this?
You> Are there any security concerns?
```

### 5. Save Important Sessions

```
You> /save before_refactor
# Make changes
You> /save after_refactor
```

### 6. Use Verbose Mode for Debugging

```
You> /verbose
You> Fix the failing test
# See detailed Worker output to understand what's happening
```

---

<p align="center">
  <strong>Now you're ready to work with your AI Software Team!</strong>
</p>

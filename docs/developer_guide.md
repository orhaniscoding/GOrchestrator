# Developer Guide

This guide is for developers who want to understand, extend, or contribute to GOrchestrator.

## Table of Contents

- [Project Structure](#project-structure)
- [Development Setup](#development-setup)
- [Core Concepts](#core-concepts)
- [Adding New Tools](#adding-new-tools)
- [Customizing the UI](#customizing-the-ui)
- [Adding Slash Commands](#adding-slash-commands)
- [Testing](#testing)
- [Code Style](#code-style)

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
│   │   ├── __init__.py         # Exports public API
│   │   ├── config.py           # Pydantic settings
│   │   ├── manager.py          # Manager Agent (LLM)
│   │   ├── worker.py           # Worker subprocess wrapper
│   │   └── engine.py           # Session orchestration
│   │
│   ├── ui/                     # User interface
│   │   ├── __init__.py
│   │   └── console.py          # Rich terminal UI
│   │
│   └── utils/                  # Utilities
│       ├── __init__.py
│       └── parser.py           # JSON log parser
│
├── tests/                      # Unit tests
│   ├── __init__.py
│   ├── test_config.py          # Settings tests
│   ├── test_engine.py          # Session engine tests
│   ├── test_manager.py         # Manager agent tests
│   └── test_parser.py          # Log parser tests
│
├── docs/                       # Documentation
│   ├── setup_guide.md
│   ├── user_guide.md
│   ├── architecture.md
│   └── developer_guide.md
│
└── .gorchestrator/             # Runtime data (gitignored)
    ├── sessions/               # Saved sessions
    └── gorchestrator.log       # Application log file
```

### Module Responsibilities

| Module | Purpose |
|--------|---------|
| `core/config.py` | Settings management via pydantic-settings |
| `core/manager.py` | LLM-powered Manager Agent with tool calling |
| `core/worker.py` | Subprocess wrapper for Mini-SWE-GOCore |
| `core/engine.py` | Session loop and command handling |
| `ui/console.py` | Rich terminal interface |
| `utils/parser.py` | Parse Worker JSON logs |

---

## Development Setup

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/GOrchestrator.git
cd GOrchestrator

# Create virtual environment
uv venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install in development mode
uv sync
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Run in Development

```bash
# Run directly
uv run python main.py

# Or with auto-reload (if using a tool like watchdog)
uv run watchmedo auto-restart --pattern="*.py" -- python main.py
```

---

## Core Concepts

### 1. The Manager Agent

The Manager Agent (`src/core/manager.py`) is the heart of GOrchestrator.

```python
class ManagerAgent:
    def __init__(self, settings, on_worker_output, on_thinking):
        self.settings = settings
        self.worker = AgentWorker(settings)
        self.messages = []  # Conversation history

        # Callbacks for UI integration
        self.on_worker_output = on_worker_output
        self.on_thinking = on_thinking

        # Initialize with system prompt
        self._add_system_message()

    def chat(self, user_message: str) -> ManagerResponse:
        """Main entry point for user messages."""
        # 1. Add user message to history
        # 2. Call LLM with tools
        # 3. Handle any tool calls
        # 4. Return final response
```

### 2. Tool Calling

Tools are defined as JSON schemas that the LLM can call:

```python
WORKER_TOOL = {
    "type": "function",
    "function": {
        "name": "delegate_to_worker",
        "description": "...",
        "parameters": {
            "type": "object",
            "properties": {
                "task_description": {"type": "string", "description": "..."},
            },
            "required": ["task_description"]
        }
    }
}
```

### 3. Session Persistence

Sessions are saved as JSON files in `.gorchestrator/sessions/`:

```python
def save_session(self, name: str) -> Path:
    session_data = {
        "version": "2.0",
        "saved_at": datetime.now().isoformat(),
        "manager_history": self.manager.export_history()
    }
    # Save to file
```

---

## Adding New Tools

You can extend the Manager with additional tools beyond `delegate_to_worker`.

### Step 1: Define the Tool Schema

```python
# In src/core/manager.py

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for information",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    }
}
```

### Step 2: Add Tool to Available Tools

```python
# Update the tools list in _call_llm()
if include_tools:
    kwargs["tools"] = [WORKER_TOOL, WEB_SEARCH_TOOL]
```

### Step 3: Implement Tool Handler

```python
def _handle_tool_calls(self, tool_calls: list[dict]) -> list[Any]:
    results = []

    for tool_call in tool_calls:
        name = tool_call["function"]["name"]
        args = json.loads(tool_call["function"]["arguments"])

        if name == "delegate_to_worker":
            result = self._execute_worker_task(args["task_description"])
        elif name == "web_search":
            result = self._execute_web_search(args["query"], args.get("num_results", 5))

        results.append(result)

    return results

def _execute_web_search(self, query: str, num_results: int) -> str:
    """Execute a web search."""
    # Implement search logic
    # Return results as string for LLM context
    return f"Search results for '{query}': ..."
```

### Step 4: Update System Prompt (Optional)

Add instructions about the new tool:

```python
MANAGER_SYSTEM_PROMPT = """
...
You also have access to:
- `web_search(query)`: Search the web for information
...
"""
```

---

## Customizing the UI

### Adding New Display Methods

```python
# In src/ui/console.py

class ConsoleUI:
    def display_custom_panel(self, title: str, content: str, style: str = "blue"):
        """Display a custom panel with specified styling."""
        panel = Panel(
            Markdown(content),
            title=f"[bold {style}]{title}[/bold {style}]",
            border_style=style,
            padding=(0, 1),
        )
        self.console.print(panel)

    def display_code_block(self, code: str, language: str = "python"):
        """Display syntax-highlighted code."""
        from rich.syntax import Syntax
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        self.console.print(syntax)

    def display_progress_bar(self, description: str, total: int):
        """Create a progress bar context manager."""
        from rich.progress import Progress, BarColumn, TextColumn
        return Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
        )
```

### Customizing the Theme

```python
# In src/ui/console.py

GORCHESTRATOR_THEME = Theme({
    # Existing styles
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",

    # Add custom styles
    "code": "green on black",
    "highlight": "bold yellow",
    "muted": "dim white",

    # Role-specific
    "user": "bold green",
    "manager": "bold cyan",
    "worker": "dim white",
})
```

### Adding Emoji/Icon Customization

```python
class ConsoleUI:
    # Make icons configurable
    ICONS = {
        "user": "👤",
        "manager": "🧠",
        "worker": "👷",
        "success": "✓",
        "error": "✗",
        "warning": "⚠",
        "info": "ℹ",
    }

    def __init__(self, use_emoji: bool = True):
        self.use_emoji = use_emoji
        if not use_emoji:
            self.ICONS = {k: "" for k in self.ICONS}
```

---

## Adding Slash Commands

### Step 1: Add Handler in Engine

```python
# In src/core/engine.py

def _handle_slash_command(self, command: str) -> bool:
    parts = command.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    # ... existing commands ...

    elif cmd == "/export":
        self._handle_export_command(arg)
        return True

    elif cmd == "/model":
        self._handle_model_command(arg)
        return True

    return False

def _handle_export_command(self, filename: str):
    """Export conversation to markdown."""
    filename = filename or "conversation.md"

    content = "# GOrchestrator Conversation\n\n"
    for msg in self.manager.messages:
        if msg.role.value == "user":
            content += f"## 👤 User\n{msg.content}\n\n"
        elif msg.role.value == "assistant":
            content += f"## 🧠 Manager\n{msg.content}\n\n"

    with open(filename, "w") as f:
        f.write(content)

    self.ui.print_success(f"Exported to {filename}")

def _handle_model_command(self, model_name: str):
    """Change the Manager model."""
    if not model_name:
        self.ui.print_info(f"Current model: {self.settings.ORCHESTRATOR_MODEL}")
        return

    # Update model (would need settings refresh)
    self.ui.print_success(f"Model changed to: {model_name}")
```

### Step 2: Update Help

```python
def _show_help(self):
    help_text = """
    ...
    | `/export [file]` | Export conversation to markdown |
    | `/model [name]` | Change Manager model |
    ...
    """
```

---

## Testing

### Unit Tests

```python
# tests/test_parser.py

import pytest
from src.utils.parser import parse_log_line, AgentLogEntry, RawLogEntry

def test_parse_step_log():
    line = '{"type": "step", "step": 1, "message": "Starting..."}'
    entry = parse_log_line(line)

    assert isinstance(entry, AgentLogEntry)
    assert entry.is_step
    assert entry.step_number == 1
    assert entry.message == "Starting..."

def test_parse_raw_line():
    line = "Some plain text output"
    entry = parse_log_line(line)

    assert isinstance(entry, RawLogEntry)
    assert entry.log_type == "raw"

def test_parse_invalid_json():
    line = '{"broken json'
    entry = parse_log_line(line)

    assert isinstance(entry, RawLogEntry)
```

### Integration Tests

```python
# tests/test_manager.py

import pytest
from unittest.mock import Mock, patch
from src.core.manager import ManagerAgent

@pytest.fixture
def manager():
    settings = Mock()
    settings.ORCHESTRATOR_MODEL = "test-model"
    settings.get_orchestrator_config.return_value = {
        "model": "test-model",
        "api_base": "http://test",
        "api_key": "test-key"
    }
    return ManagerAgent(settings=settings)

def test_manager_initialization(manager):
    assert len(manager.messages) == 1  # System prompt
    assert manager.messages[0].role.value == "system"

@patch('src.core.manager.completion')
def test_manager_chat(mock_completion, manager):
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "Hello!"
    mock_response.choices[0].message.tool_calls = None
    mock_completion.return_value = mock_response

    response = manager.chat("Hi")

    assert response.content == "Hello!"
    assert len(manager.messages) == 3  # system + user + assistant
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/test_parser.py -v
```

---

## Code Style

### Formatting

We use [Black](https://black.readthedocs.io/) for formatting and [isort](https://pycqa.github.io/isort/) for import sorting.

```bash
# Format code
uv run black src/ tests/
uv run isort src/ tests/

# Check without modifying
uv run black --check src/
```

### Type Hints

All code should use type hints:

```python
# Good
def parse_log_line(line: str) -> LogEntry:
    ...

def run_task(
    self,
    task: str,
    model: str = "claude-3-5-sonnet-20241022",
    on_output: Callable[[str], None] | None = None,
) -> TaskResult:
    ...

# Check types
uv run mypy src/
```

### Docstrings

Use Google-style docstrings:

```python
def chat(self, user_message: str) -> ManagerResponse:
    """
    Process a user message and generate a response.

    This may involve multiple LLM calls if tool use is required.

    Args:
        user_message: The user's input message.

    Returns:
        ManagerResponse with content and any worker results.

    Raises:
        RuntimeError: If LLM call fails after retries.
    """
```

---

## Debugging Tips

### Application Logs

GOrchestrator automatically logs to `.gorchestrator/gorchestrator.log`. Check this file for errors and debug information:

```bash
# View recent logs
tail -f .gorchestrator/gorchestrator.log

# On Windows PowerShell
Get-Content .gorchestrator\gorchestrator.log -Tail 50 -Wait
```

### Debug LLM Calls

```python
# In manager.py
import litellm
litellm.set_verbose = True  # Shows all API calls
```

### Inspect Messages

```python
# Add to manager.py for debugging
def _debug_messages(self):
    for i, msg in enumerate(self.messages):
        print(f"[{i}] {msg.role.value}: {msg.content[:50]}...")
```

---

<p align="center">
  <strong>Happy coding! We look forward to your contributions.</strong>
</p>

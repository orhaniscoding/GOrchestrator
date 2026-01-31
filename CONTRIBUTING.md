# Contributing to GOrchestrator

Thank you for your interest in contributing to GOrchestrator! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Development Workflow](#development-workflow)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Reporting Issues](#reporting-issues)

---

## Code of Conduct

This project adheres to a Code of Conduct that all contributors are expected to follow:

- **Be respectful**: Treat everyone with respect and consideration
- **Be constructive**: Provide helpful feedback and suggestions
- **Be inclusive**: Welcome newcomers and help them get started
- **Be patient**: Remember that everyone has different skill levels

---

## Getting Started

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Git
- A running instance of Antigravity Manager (for testing)

### Development Setup

1. **Fork the repository**

   Click the "Fork" button on GitHub to create your own copy.

2. **Clone your fork**

   ```bash
   git clone https://github.com/YOUR_USERNAME/GOrchestrator.git
   cd GOrchestrator
   ```

3. **Set up the development environment**

   ```bash
   # Create virtual environment
   uv venv

   # Activate it
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate

   # Install dependencies
   uv sync
   ```

4. **Configure environment**

   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Verify setup**

   ```bash
   uv run python main.py
   # Should start the application
   ```

---

## How to Contribute

### Types of Contributions

| Type | Description |
|------|-------------|
| 🐛 **Bug Fixes** | Fix issues and improve stability |
| ✨ **Features** | Add new functionality |
| 📚 **Documentation** | Improve docs, add examples |
| 🧪 **Tests** | Add or improve test coverage |
| 🎨 **UI/UX** | Improve the terminal interface |
| 🔧 **Refactoring** | Improve code quality |

### Finding Issues to Work On

- Look for issues labeled `good first issue` for beginner-friendly tasks
- Check `help wanted` for issues where we need community help
- Browse the [project board](https://github.com/yourusername/GOrchestrator/projects) for planned features

### Proposing New Features

Before starting work on a major feature:

1. Check existing issues to see if it's already proposed
2. Open a new issue describing your idea
3. Wait for feedback from maintainers
4. Once approved, you can start implementation

---

## Development Workflow

### 1. Create a Branch

```bash
# Sync with upstream
git fetch origin
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### Branch Naming Convention

| Prefix | Use Case |
|--------|----------|
| `feature/` | New features |
| `fix/` | Bug fixes |
| `docs/` | Documentation changes |
| `refactor/` | Code refactoring |
| `test/` | Adding tests |

### 2. Make Changes

- Write clean, readable code
- Follow the [coding standards](#coding-standards)
- Add tests for new functionality
- Update documentation as needed

### 3. Test Your Changes

```bash
# Run the application
uv run python main.py

# Run tests
uv run pytest

# Check code style
uv run black --check src/
uv run mypy src/
```

### 4. Commit Your Changes

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Format
<type>(<scope>): <description>

# Examples
feat(manager): add web search tool
fix(worker): handle encoding errors on Windows
docs(readme): update installation instructions
test(parser): add tests for edge cases
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `test`: Tests
- `refactor`: Code refactoring
- `style`: Code style (formatting, etc.)
- `chore`: Maintenance tasks

### 5. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then open a Pull Request on GitHub.

---

## Pull Request Process

### PR Checklist

Before submitting your PR, ensure:

- [ ] Code follows the project's style guidelines
- [ ] All tests pass locally
- [ ] New code has appropriate test coverage
- [ ] Documentation is updated if needed
- [ ] Commit messages follow conventions
- [ ] PR description explains the changes

### PR Template

When creating a PR, please include:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Refactoring

## Testing
How did you test these changes?

## Related Issues
Closes #123

## Screenshots (if applicable)
```

### Review Process

1. Maintainers will review your PR
2. Address any requested changes
3. Once approved, your PR will be merged
4. Delete your branch after merging

---

## Coding Standards

### Python Style

We follow [PEP 8](https://pep8.org/) with these tools:

```bash
# Format code
uv run black src/ tests/

# Sort imports
uv run isort src/ tests/

# Type checking
uv run mypy src/
```

### Code Organization

```python
# File structure
"""
Module docstring explaining purpose.
"""

# Standard library imports
import json
import logging
from pathlib import Path

# Third-party imports
from rich.console import Console
import litellm

# Local imports
from .config import Settings
from ..utils.parser import parse_log_line

# Constants
DEFAULT_MODEL = "claude-3-5-sonnet-20241022"

# Logger
logger = logging.getLogger(__name__)


# Classes and functions
class MyClass:
    """Class docstring."""

    def my_method(self, arg: str) -> str:
        """Method docstring."""
        pass
```

### Type Hints

All functions should have type hints:

```python
# Good
def process_message(
    message: str,
    context: dict[str, Any] | None = None,
) -> ProcessResult:
    ...

# Avoid
def process_message(message, context=None):
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def complex_function(
    param1: str,
    param2: int,
    optional: bool = False,
) -> dict[str, Any]:
    """
    Brief description of function.

    Longer description if needed, explaining behavior,
    edge cases, or important details.

    Args:
        param1: Description of param1.
        param2: Description of param2.
        optional: Description of optional param.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param1 is empty.
        RuntimeError: When external service fails.

    Example:
        >>> result = complex_function("test", 42)
        >>> print(result["status"])
        "success"
    """
```

### Error Handling

```python
# Good - specific exceptions with context
try:
    result = external_api_call()
except ConnectionError as e:
    logger.error(f"API connection failed: {e}")
    raise RuntimeError(f"Failed to connect to API: {e}") from e

# Avoid - bare except
try:
    result = external_api_call()
except:
    pass
```

---

## Reporting Issues

### Bug Reports

When reporting bugs, please include:

1. **Description**: Clear description of the bug
2. **Steps to Reproduce**: Minimal steps to reproduce
3. **Expected Behavior**: What should happen
4. **Actual Behavior**: What actually happens
5. **Environment**: OS, Python version, etc.
6. **Logs**: Relevant error messages or logs

### Bug Report Template

```markdown
## Bug Description
A clear description of what the bug is.

## Steps to Reproduce
1. Start GOrchestrator with '...'
2. Enter command '...'
3. See error

## Expected Behavior
What you expected to happen.

## Actual Behavior
What actually happened.

## Environment
- OS: Windows 11 / macOS 14 / Ubuntu 22.04
- Python: 3.11.5
- GOrchestrator version: 0.1.0

## Logs
```
Paste relevant logs here
```

## Additional Context
Any other context about the problem.
```

### Feature Requests

For feature requests, please describe:

1. **Problem**: What problem does this solve?
2. **Solution**: Your proposed solution
3. **Alternatives**: Alternative solutions considered
4. **Context**: Why this would be valuable

---

## Recognition

Contributors will be recognized in:

- The project's README
- Release notes when their changes are included
- The CONTRIBUTORS file

---

## Questions?

If you have questions about contributing:

- Open a [Discussion](https://github.com/yourusername/GOrchestrator/discussions)
- Ask in an issue with the `question` label
- Reach out to maintainers

---

<p align="center">
  <strong>Thank you for contributing to GOrchestrator! 🎉</strong>
</p>

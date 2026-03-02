# Review Scope

## Target

GOrchestrator - Full project comprehensive review covering:
- Functionality consistency and command synchronization
- UI/UX visual consistency
- Test completeness and correctness
- Documentation accuracy and currency
- Settings persistence and validation
- AI usability (both human and AI agent usage)
- GitHub readiness (CI, .gitignore, secrets)

## Files

### Source Code (src/)
#### src/core/ (8 Python + 8 YAML profiles)
- `src/core/__init__.py`
- `src/core/config.py` — Settings (pydantic-settings), detect_provider(), SANITIZE_RE
- `src/core/engine.py` — Session engine, WorkerRegistry, slash commands
- `src/core/llm_pool.py` — Parallel multi-LLM execution pool
- `src/core/manager.py` — Manager Agent (LiteLLM unified routing)
- `src/core/sub_manager.py` — Sub-Manager advisory agents
- `src/core/team.py` — Team management
- `src/core/worker.py` — Worker subprocess wrapper
- `src/core/manager_profiles/` — 5 YAML profiles (advanced, custom, default, minimal, rules)
- `src/core/sub_manager_profiles/` — 3 YAML profiles (architect, performance, security)

#### src/commands/ (4 files)
- `src/commands/parser.py` — CommandParser, SOURCES, COMMAND_TREE
- `src/commands/handlers.py` — CommandHandler
- `src/commands/completer.py` — Tab completion
- `src/commands/help.py` — Help system

#### src/ui/ (1 file)
- `src/ui/console.py` — Rich terminal UI, dashboard

#### src/utils/ (1 file)
- `src/utils/parser.py` — Worker JSON log parser

### Tests (8 files)
- `tests/test_config.py`
- `tests/test_engine.py`
- `tests/test_manager.py`
- `tests/test_llm_pool.py`
- `tests/test_sub_manager.py`
- `tests/test_commands_parser.py`
- `tests/test_parser.py`

### Documentation (8 files)
- `README.md`
- `CLAUDE.md`
- `CONTRIBUTING.md`
- `docs/architecture.md`
- `docs/developer_guide.md`
- `docs/setup_guide.md`
- `docs/user_guide.md`
- `docs/SYSTEM_DIAGRAM.md`

### Configuration (5 files)
- `.env.example`
- `pyproject.toml`
- `.github/workflows/ci.yml`
- `main.py` (entry point)

## Flags

- Security Focus: no
- Performance Critical: no
- Strict Mode: no
- Framework: Python / LiteLLM / Rich / prompt_toolkit / pydantic-settings

## Review Phases

1. Code Quality & Architecture
2. Security & Performance
3. Testing & Documentation
4. Best Practices & Standards
5. Consolidated Report

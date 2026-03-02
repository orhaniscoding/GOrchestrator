# GOrchestrator Git Cleanup + Test Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Safely commit 7,031+ lines of uncommitted work in 9 logical commits, push to remote, then fix 16 failing engine tests.

**Architecture:** Layered commit strategy following dependency order (infrastructure → config → features → commands → UI → worker core → engine → tests → docs). Test fix phase diagnoses and repairs engine test fixture infrastructure.

**Tech Stack:** Git, Python 3.11+, uv, pytest

---

## Phase 1: Git Cleanup (9 Commits)

### Task 1: Core Infrastructure Commit

**Files:**
- Stage (untracked): `src/core/json_registry.py`
- Stage (untracked): `src/core/worker_registry.py`
- Stage (untracked): `src/core/checkpoint_manager.py`

**Step 1: Verify files exist and are untracked**

Run:
```bash
cd C:/Users/Orhan/Documents/Github/Gorchestrator/GOrchestrator
git status src/core/json_registry.py src/core/worker_registry.py src/core/checkpoint_manager.py
```
Expected: All three show as `??` (untracked)

**Step 2: Stage the files**

```bash
git add src/core/json_registry.py src/core/worker_registry.py src/core/checkpoint_manager.py
```

**Step 3: Verify staging is correct**

```bash
git status --short
```
Expected: Three files show as `A` (added), everything else unchanged

**Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: add generic JsonRegistry base and extract WorkerRegistry, CheckpointManager

- JsonRegistry[T]: generic JSON-backed persistent registry base class
- WorkerRegistry: extends JsonRegistry for worker config management
- CheckpointManager: extracted git checkpoint/undo system from engine.py
EOF
)"
```

**Step 5: Verify commit**

```bash
git log --oneline -1
```
Expected: Shows the new commit message

---

### Task 2: Configuration Commit

**Files:**
- Stage (modified): `src/core/config.py`
- Stage (untracked): `src/core/manager_profiles/` (directory)
- Stage (untracked): `src/core/sub_manager_profiles/` (directory)
- Stage (modified): `.env.example`

**Step 1: Stage the files**

```bash
cd C:/Users/Orhan/Documents/Github/Gorchestrator/GOrchestrator
git add src/core/config.py src/core/manager_profiles/ src/core/sub_manager_profiles/ .env.example
```

**Step 2: Verify staging**

```bash
git diff --cached --stat
```
Expected: Shows config.py modifications, new profile directories, .env.example changes

**Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: add config improvements, manager profiles, and env persistence

- Enhanced Settings with manager/worker profile support
- Added manager_profiles/ and sub_manager_profiles/ YAML directories
- Updated .env.example with new profile configuration options
- Improved detect_provider() and write_env_value() functions
EOF
)"
```

**Step 4: Verify**

```bash
git log --oneline -2
```

---

### Task 3: Manager Ecosystem Commit

**Files:**
- Stage (untracked): `src/core/sub_manager.py`
- Stage (untracked): `src/core/llm_pool.py`
- Stage (untracked): `src/core/team.py`
- Stage (modified): `src/core/manager.py`
- Stage (modified): `src/core/worker.py`

**Step 1: Stage the files**

```bash
cd C:/Users/Orhan/Documents/Github/Gorchestrator/GOrchestrator
git add src/core/sub_manager.py src/core/llm_pool.py src/core/team.py src/core/manager.py src/core/worker.py
```

**Step 2: Verify staging**

```bash
git diff --cached --stat
```
Expected: 3 new files + 2 modified files staged

**Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: add SubManager advisors, LLM Pool, and Team management

- SubManager: advisory agents using Mixture of Agents pattern
- LLMPool: parallel multi-LLM execution with response synthesis
- Team: reusable Manager + SubManager combination presets
- Manager: updated with sub-manager consultation and dynamic tool generation
- Worker: enhanced subprocess wrapper with env allowlist
EOF
)"
```

**Step 4: Verify**

```bash
git log --oneline -3
```

---

### Task 4: Command System Commit

**Files:**
- Stage (untracked): `src/commands/` (entire directory)

**Step 1: Stage the directory**

```bash
cd C:/Users/Orhan/Documents/Github/Gorchestrator/GOrchestrator
git add src/commands/
```

**Step 2: Verify staging**

```bash
git diff --cached --stat
```
Expected: __init__.py, parser.py, handlers.py, completer.py, help.py all staged

**Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: add slash command system with parser, handlers, completer, and help

- CommandParser: parses user input into Command(source, action, args, options)
- CommandHandler: routes parsed commands to SessionEngine methods
- Completer: prompt_toolkit tab-completion for all slash commands
- Help: formatted help text generation via Rich
EOF
)"
```

**Step 4: Verify**

```bash
git log --oneline -4
```

---

### Task 5: Terminal UI Commit

**Files:**
- Stage (modified): `src/ui/console.py`

**Step 1: Stage the file**

```bash
cd C:/Users/Orhan/Documents/Github/Gorchestrator/GOrchestrator
git add src/ui/console.py
```

**Step 2: Verify staging**

```bash
git diff --cached --stat
```
Expected: console.py with ~351 lines added

**Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: update Rich terminal UI with dashboard and worker streaming

- Startup dashboard panel showing session, manager, workers, mode
- Real-time worker output streaming with step-by-step progress
- TaskResult formatting with cost, step count, success/failure
- Conversation history display and prompt rendering
EOF
)"
```

**Step 4: Verify**

```bash
git log --oneline -5
```

---

### Task 6: Worker Core Integration Commit

**Files:**
- Stage (untracked): `src/worker_core/` (entire directory)

**Step 1: Stage the directory**

```bash
cd C:/Users/Orhan/Documents/Github/Gorchestrator/GOrchestrator
git add src/worker_core/
```

**Step 2: Verify staging**

```bash
git diff --cached --stat
```
Expected: All worker_core files staged (minisweagent package, configs, etc.)

**Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: integrate Mini-SWE-GOCore as embedded worker core

- Full embedded coding agent (ReAct loop with bash, file I/O, search tools)
- Worker profiles: live (quick edits) and livesweagent (complex SWE tasks)
- Headless JSON Lines output for automation-friendly subprocess communication
- Proxy-routed LLM calls through configurable API endpoints
EOF
)"
```

**Step 4: Verify**

```bash
git log --oneline -6
```

---

### Task 7: Session Engine Commit

**Files:**
- Stage (modified): `src/core/engine.py`
- Stage (modified): `src/__init__.py`
- Stage (modified): `src/core/__init__.py`
- Stage (modified): `main.py`

**Step 1: Stage the files**

```bash
cd C:/Users/Orhan/Documents/Github/Gorchestrator/GOrchestrator
git add src/core/engine.py src/__init__.py src/core/__init__.py main.py
```

**Step 2: Verify staging**

```bash
git diff --cached --stat
```
Expected: engine.py with ~1,900 lines added, plus init and main.py changes

**Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: update SessionEngine with full command routing and session management

- Complete slash command routing for worker/submanager/team/config/session
- Session lifecycle: create/save/load/resume with unique IDs and random names
- WorkerRegistry integration for persistent worker management
- Git checkpoint integration before every worker task
- Interactive REPL with prompt_toolkit and Rich dashboard
- Removed sys.path.insert hack, consolidated entry point
EOF
)"
```

**Step 4: Verify**

```bash
git log --oneline -7
```

---

### Task 8: Test Suite Commit

**Files:**
- Stage (untracked): `tests/test_checkpoint_manager.py`
- Stage (untracked): `tests/test_commands_parser.py`
- Stage (untracked): `tests/test_handlers.py`
- Stage (untracked): `tests/test_llm_pool.py`
- Stage (untracked): `tests/test_sub_manager.py`
- Stage (untracked): `tests/test_team.py`
- Stage (untracked): `tests/test_worker.py`
- Stage (modified): `tests/test_engine.py`
- Stage (modified): `tests/test_manager.py`
- Stage (modified): `tests/test_config.py`
- Stage (untracked): `test_proxy.json`

NOTE: Do NOT stage `tests/test_parser.py` here — it is listed as modified but belongs logically with the utils parser (included via engine changes already).

**Step 1: Stage the files**

```bash
cd C:/Users/Orhan/Documents/Github/Gorchestrator/GOrchestrator
git add tests/test_checkpoint_manager.py tests/test_commands_parser.py tests/test_handlers.py tests/test_llm_pool.py tests/test_sub_manager.py tests/test_team.py tests/test_worker.py tests/test_engine.py tests/test_manager.py tests/test_config.py tests/test_parser.py test_proxy.json
```

**Step 2: Verify staging**

```bash
git diff --cached --stat
```
Expected: 7 new test files + 4 modified test files + test_proxy.json

**Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
test: add comprehensive test suite (282 tests across 12 files)

- test_checkpoint_manager: git checkpoint/undo system tests
- test_commands_parser: command parsing and COMMAND_TREE tests
- test_handlers: command handler dispatch tests
- test_llm_pool: LLM Pool CRUD and parallel execution tests
- test_sub_manager: SubManager registry tests
- test_team: Team registry CRUD, activate/deactivate tests
- test_worker: Worker command building, env allowlist, noise filtering tests
- Updated test_engine, test_manager, test_config with expanded coverage
EOF
)"
```

**Step 4: Verify**

```bash
git log --oneline -8
```

---

### Task 9: Documentation Commit

**Files:**
- Stage (untracked): `CHANGELOG.md`, `CLAUDE.md`, `SECURITY.md`, `SECURITY_AUDIT.md`
- Stage (untracked): `docs/SYSTEM_DIAGRAM.md`, `docs/plans/`
- Stage (untracked): `.github/`, `.full-review/`
- Stage (modified): `README.md`, `CONTRIBUTING.md`
- Stage (modified): `docs/architecture.md`, `docs/developer_guide.md`, `docs/setup_guide.md`, `docs/user_guide.md`
- Stage (modified): `pyproject.toml`, `uv.lock`

**Step 1: Stage all remaining files**

```bash
cd C:/Users/Orhan/Documents/Github/Gorchestrator/GOrchestrator
git add CHANGELOG.md CLAUDE.md SECURITY.md SECURITY_AUDIT.md docs/SYSTEM_DIAGRAM.md docs/plans/ .github/ .full-review/ README.md CONTRIBUTING.md docs/architecture.md docs/developer_guide.md docs/setup_guide.md docs/user_guide.md pyproject.toml uv.lock
```

**Step 2: Verify nothing is left uncommitted**

```bash
git status
```
Expected: Only `.env` and `.gorchestrator/` should remain as untracked/ignored (gitignored items). NO other modified or untracked files.

**Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
docs: add complete documentation, security audits, and project metadata

- CHANGELOG.md: v0.1.1 release notes with security fixes and new features
- CLAUDE.md: AI assistant project guide with architecture and conventions
- SECURITY.md: vulnerability disclosure policy
- SECURITY_AUDIT.md: comprehensive security audit report
- Updated README, CONTRIBUTING, architecture, developer/user/setup guides
- Added SYSTEM_DIAGRAM.md, GitHub workflows, full-review artifacts
- Updated pyproject.toml with dependency pins and consolidated entry point
EOF
)"
```

**Step 4: Final verification — clean working tree**

```bash
git status
git log --oneline -9
```
Expected: Clean working tree (only gitignored files). 9 new commits visible.

---

### Task 10: Pull and Push to Remote

**Step 1: Pull to check for conflicts**

```bash
cd C:/Users/Orhan/Documents/Github/Gorchestrator/GOrchestrator
git pull origin main --rebase
```
Expected: "Already up to date" or successful rebase (repo was up to date with origin/main)

**Step 2: Push all commits**

```bash
git push origin main
```
Expected: 9 new commits pushed successfully

**Step 3: Verify remote is in sync**

```bash
git log --oneline -10
git status
```
Expected: Clean status, all commits visible, branch up to date with origin/main

---

## Phase 2: Fix 16 Failing Engine Tests

### Task 11: Identify Failing Tests

**Files:**
- Investigate: `tests/test_engine.py`

**Step 1: Run engine tests to identify failures**

```bash
cd C:/Users/Orhan/Documents/Github/Gorchestrator/GOrchestrator
uv run pytest tests/test_engine.py -v 2>&1 | tail -60
```
Expected: Output showing which 16 tests fail and their error messages

**Step 2: Capture the exact failure list**

```bash
uv run pytest tests/test_engine.py -v --tb=short 2>&1 | grep -E "FAILED|ERROR"
```
Expected: List of 16 failing test names with brief error descriptions

**Step 3: Document findings**

Record:
- Exact test names that fail
- Common error patterns (e.g., missing fixture, wrong mock, missing attribute)
- Whether failures cluster around a specific fixture or test class

---

### Task 12: Diagnose Root Cause

**Files:**
- Read: `tests/test_engine.py`
- Read: `src/core/engine.py` (relevant sections only)

**Step 1: Read the test file to understand fixture setup**

Focus on:
- `@pytest.fixture` definitions at the top of the file
- Test class `setUp` / `setUpClass` methods if any
- Common mock/patch patterns used across failing tests
- Import statements at the top

**Step 2: Compare fixture expectations with actual engine API**

Check:
- Do fixtures create `SessionEngine` with correct constructor args?
- Are mocked methods/attributes still named the same in `engine.py`?
- Are patches targeting the correct import paths?
- Has `CommandHandler` interface changed without test updates?

**Step 3: Identify the specific infrastructure issue**

Per CLAUDE.md: "16 engine tests fail due to test fixture infrastructure issues"
Per CHANGELOG: "CommandHandler._handle_worker() was not forwarding cmd.args to sub-handlers"

Likely root cause: Test fixtures don't match the refactored engine API (new command system, extracted registries, etc.)

---

### Task 13: Fix the Failing Tests

**Files:**
- Modify: `tests/test_engine.py`

**Step 1: Apply fixture fixes based on diagnosis**

Fix the identified issues. Common patterns to fix:
- Update constructor arguments to match new `SessionEngine.__init__()` signature
- Update mock paths to match extracted modules (e.g., `src.core.worker_registry` instead of `src.core.engine`)
- Update command handler test expectations for new `CommandHandler` dispatch
- Add missing fixture attributes for new dependencies (registries, checkpoint manager)

**Step 2: Run only the previously failing tests**

```bash
uv run pytest tests/test_engine.py -v -k "test_name1 or test_name2 or ..." 2>&1
```
Expected: All 16 previously failing tests now PASS

**Step 3: Run the full engine test file**

```bash
uv run pytest tests/test_engine.py -v
```
Expected: ALL engine tests pass (0 failures)

---

### Task 14: Full Suite Verification and Final Commit

**Files:**
- Verify: All test files in `tests/`
- Commit: `tests/test_engine.py`

**Step 1: Run the complete test suite**

```bash
cd C:/Users/Orhan/Documents/Github/Gorchestrator/GOrchestrator
uv run pytest tests/ -v
```
Expected: 282 tests, ALL passing (0 failures, 0 errors)

**Step 2: Commit the test fix**

```bash
git add tests/test_engine.py
git commit -m "$(cat <<'EOF'
fix: resolve 16 failing engine test fixtures

- Updated test fixtures to match refactored SessionEngine API
- Fixed mock paths for extracted modules (worker_registry, checkpoint_manager)
- Corrected CommandHandler dispatch expectations
EOF
)"
```

**Step 3: Push the fix**

```bash
git push origin main
```

**Step 4: Final verification**

```bash
uv run pytest tests/ -v --tb=short
git status
git log --oneline -12
```
Expected: All 282 tests pass, clean working tree, 10 total new commits (9 cleanup + 1 fix)

---

## Completion Checklist

- [ ] Task 1: Core Infrastructure committed
- [ ] Task 2: Configuration committed
- [ ] Task 3: Manager Ecosystem committed
- [ ] Task 4: Command System committed
- [ ] Task 5: Terminal UI committed
- [ ] Task 6: Worker Core committed
- [ ] Task 7: Session Engine committed
- [ ] Task 8: Test Suite committed
- [ ] Task 9: Documentation committed
- [ ] Task 10: All 9 commits pushed to origin/main
- [ ] Task 11: 16 failing tests identified
- [ ] Task 12: Root cause diagnosed
- [ ] Task 13: Failing tests fixed
- [ ] Task 14: Full suite passing (282/282), fix committed and pushed

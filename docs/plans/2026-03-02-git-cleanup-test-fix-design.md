# Design: GOrchestrator Git Cleanup + Test Fix

**Date**: 2026-03-02
**Status**: Approved
**Scope**: GOrchestrator sub-project only (Mini-SWE-GOCore deferred)

---

## Problem

GOrchestrator has 7,031+ lines of uncommitted work (20 modified + 27 new files) representing a nearly complete next-generation release. Additionally, 16 engine tests fail due to test fixture infrastructure issues. This work is at risk of loss and blocks further development.

## Goals

1. Safely commit all uncommitted work in logical, layered commits (dependency order)
2. Push to remote
3. Fix the 16 failing engine tests
4. Achieve 282/282 tests passing

## Out of Scope

- Mini-SWE-GOCore cleanup (user deferred)
- New features or refactoring
- Root-level monorepo git setup

## Commit Plan (Layered, Dependency Order)

### Commit 1: Core Infrastructure
```
feat: add generic JsonRegistry base and extract WorkerRegistry, CheckpointManager

Files:
  - src/core/json_registry.py (NEW)
  - src/core/worker_registry.py (NEW)
  - src/core/checkpoint_manager.py (NEW)
```

### Commit 2: Configuration
```
feat: add config improvements, manager profiles, and env persistence

Files:
  - src/core/config.py (MODIFIED, +610 lines)
  - src/core/manager_profiles/ (NEW directory)
  - src/core/sub_manager_profiles/ (NEW directory)
```

### Commit 3: Manager Ecosystem
```
feat: add SubManager advisors, LLM Pool, and Team management

Files:
  - src/core/sub_manager.py (NEW)
  - src/core/llm_pool.py (NEW)
  - src/core/team.py (NEW)
  - src/core/manager.py (MODIFIED, +985 lines)
  - src/core/worker.py (MODIFIED)
```

### Commit 4: Command System
```
feat: add slash command system with parser, handlers, completer, and help

Files:
  - src/commands/__init__.py (NEW)
  - src/commands/parser.py (NEW)
  - src/commands/handlers.py (NEW)
  - src/commands/completer.py (NEW)
  - src/commands/help.py (NEW)
```

### Commit 5: Terminal UI
```
feat: update Rich terminal UI with dashboard and worker streaming

Files:
  - src/ui/console.py (MODIFIED, +351 lines)
```

### Commit 6: Worker Core Integration
```
feat: integrate Mini-SWE-GOCore as embedded worker core

Files:
  - src/worker_core/ (NEW directory - full embedded coding agent)
```

### Commit 7: Session Engine
```
feat: update SessionEngine with full command routing and session management

Files:
  - src/core/engine.py (MODIFIED, +1,900 lines)
```

### Commit 8: Test Suite
```
test: add comprehensive test suite (282 tests across 12 files)

Files:
  - tests/test_checkpoint_manager.py (NEW)
  - tests/test_commands_parser.py (NEW)
  - tests/test_handlers.py (NEW)
  - tests/test_llm_pool.py (NEW)
  - tests/test_sub_manager.py (NEW)
  - tests/test_team.py (NEW)
  - tests/test_worker.py (NEW)
  - tests/test_engine.py (MODIFIED, +599 lines)
  - tests/test_manager.py (MODIFIED, +462 lines)
  - tests/test_config.py (MODIFIED)
  - tests/test_parser.py (MODIFIED)
  - test_proxy.json (NEW)
```

### Commit 9: Documentation
```
docs: add complete documentation, security audits, and project metadata

Files:
  - README.md, CHANGELOG.md, CLAUDE.md, SECURITY.md, SECURITY_AUDIT.md
  - docs/architecture.md, docs/user_guide.md, docs/developer_guide.md
  - docs/setup_guide.md, docs/SYSTEM_DIAGRAM.md
  - .github/, .full-review/
  - pyproject.toml, uv.lock
```

## Test Fix Strategy

After all commits are pushed:

1. **Identify**: Run `uv run pytest tests/test_engine.py -v` to identify the 16 failing tests
2. **Diagnose**: Root cause is "test fixture infrastructure issues" per CLAUDE.md
3. **Fix**: Repair fixture setup/teardown, mock/patch configurations
4. **Verify**: Run full suite `uv run pytest tests/ -v` — target 282/282 passing
5. **Final commit**: `fix: resolve 16 failing engine test fixtures`

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Import errors in intermediate commits | Committing in dependency order |
| File misassignment between commits | `git status` verification before each commit |
| Test fix side effects | Full test suite run after fix |
| Push conflicts | `git pull` before push |

## Success Criteria

- [ ] All 9 commits created with clean, descriptive messages
- [ ] All changes pushed to `origin/main`
- [ ] 16 failing engine tests fixed
- [ ] Full test suite (282 tests) passing
- [ ] No uncommitted changes remaining

# Phase 2: Security & Performance Review

## Security Findings

### Critical (3)

| ID | Finding | CWE | File | Impact |
|----|---------|-----|------|--------|
| SEC-CRIT-01 | `write_env_value` corrupts values containing `#`, silently truncating API keys | CWE-20 | `config.py:454-476` | API keys with # get truncated on restart |
| SEC-CRIT-02 | API keys stored in plaintext JSON registry files on disk | CWE-312 | `sub_manager.py`, `llm_pool.py`, `engine.py` | All per-agent API keys readable by any filesystem user |
| SEC-CRIT-03 | Path traversal via `MANAGER_PROFILE` and `rules_file` YAML fields | CWE-22 | `config.py:282,289,347` | Arbitrary file read via crafted profile name |

### High (5)

| ID | Finding | CWE | File | Impact |
|----|---------|-----|------|--------|
| SEC-HIGH-01 | API keys leaked in LLM exception messages logged to disk | CWE-532 | `manager.py:550`, `sub_manager.py:324`, `llm_pool.py:255` | Keys extractable from log file |
| SEC-HIGH-02 | ThreadPoolExecutor instances never shut down | CWE-404 | `manager.py:305`, `sub_manager.py:252`, `llm_pool.py:64` | Thread exhaustion in long sessions |
| SEC-HIGH-03 | API key masking fails for keys <= 4 chars, exposes full key | CWE-200 | `handlers.py:179`, `engine.py:1331` | Short keys fully visible |
| SEC-HIGH-04 | AGENT_PATH allows arbitrary directory as worker subprocess CWD | CWE-427 | `config.py:251-256`, `worker.py:191` | Worker runs in attacker-controlled directory |
| SEC-HIGH-05 | No HTTPS enforcement — API keys transmitted over plaintext HTTP | CWE-319 | `config.py:397-405` | Keys sniffable on non-localhost endpoints |

### Medium (7)

| ID | Finding | CWE | File |
|----|---------|-----|------|
| SEC-MED-01 | Worker profile name passed to subprocess without validation | CWE-20 | `worker.py:100-107` |
| SEC-MED-02 | No file permission restrictions on sensitive config files | CWE-732 | All registry `_save()` methods |
| SEC-MED-03 | Session files store full unredacted conversation history | CWE-922 | `engine.py:483` |
| SEC-MED-04 | JSON registry deserialization trusts all fields | CWE-502 | `engine.py:125-127`, `sub_manager.py:69-71` |
| SEC-MED-05 | Dual command routing creates inconsistent state | CWE-754 | `engine.py:727-734` |
| SEC-MED-06 | `lru_cache` singleton prevents secure credential rotation | CWE-401 | `config.py:424` |
| SEC-MED-07 | Error messages expose internal API base URLs and model names | CWE-209 | `engine.py:1045-1073` |

### Low (4)

| ID | Finding | CWE | File |
|----|---------|-----|------|
| SEC-LOW-01 | CI pipeline has no SAST, dependency scanning, or secret detection | CWE-1395 | `ci.yml` |
| SEC-LOW-02 | Atomic write uses predictable `.tmp` file path (TOCTOU) | CWE-377 | `config.py:479-482` |
| SEC-LOW-03 | Dependencies unpinned — supply chain risk | CWE-1357 | `pyproject.toml` |
| SEC-LOW-04 | Git checkpoint commit message includes unsanitized LLM content | CWE-117 | `engine.py:645` |

### Positive Security Observations
- `yaml.safe_load()` correctly used (no YAML deserialization attacks)
- List-based `subprocess.Popen` (no `shell=True`) — prevents shell injection
- Environment variable allowlist for subprocesses — prevents credential leakage
- Path traversal check on session identifiers — rejects `..`, `/`, `\`
- Name sanitization via `SANITIZE_RE` — restricts to `[a-zA-Z0-9_-]`
- Git tag format validation regex — prevents forged checkpoint tags
- `ALLOWED_KEYS` whitelist for `.env` writes — restricts modifiable config
- Worker process termination with SIGKILL fallback — prevents zombies

---

## Performance Findings

### High (1)

| ID | Finding | File | Impact |
|----|---------|------|--------|
| PERF-HIGH-01 | `self.messages` list is unbounded — entire list serialized on every LLM call | `manager.py:298,514` | Token cost grows unboundedly, eventually hits context window limit |

### Medium (5)

| ID | Finding | File | Impact |
|----|---------|------|--------|
| PERF-MED-01 | ThreadPoolExecutor(8) created but never `.shutdown()` — 16+ leaked threads | `manager.py:305`, `llm_pool.py:64` | Resource leak, thread exhaustion |
| PERF-MED-02 | `_auto_save()` is synchronous blocking file I/O on main REPL thread | `engine.py:609-612` | Latency after every user turn |
| PERF-MED-03 | `session.json` grows without bound; full file rewritten every save | `engine.py:464` | Write amplification proportional to session length squared |
| PERF-MED-04 | Subprocess PIPE buffer saturation risk on slow `on_output` callbacks | `worker.py:201-210` | Worker process stalls mid-execution |
| PERF-MED-05 | `ThreadPoolExecutor` size hard-coded to 8 regardless of actual LLM count | `llm_pool.py:64` | Wasted threads or queued submissions |

### Low (7)

| ID | Finding | File | Impact |
|----|---------|------|--------|
| PERF-LOW-01 | Double `model_dump()` call on same tool_calls list | `manager.py:981,993` | Wasteful double serialization |
| PERF-LOW-02 | Second `process.wait()` after `kill()` is uncaught — potential zombie | `worker.py:148-161` | Zombie process on timeout |
| PERF-LOW-03 | ANSI regex not pre-compiled; linear noise pattern scan per line | `worker.py:21-29,139-146` | Minor overhead per output line |
| PERF-LOW-04 | `messages` list shared across threads without copy in LLMPool | `llm_pool.py:294` | Latent thread-safety mutation risk |
| PERF-LOW-05 | `.env` read-modify-write with no file lock (TOCTOU under concurrency) | `config.py:459-482` | Race condition if ever called from threads |
| PERF-LOW-06 | YAML profile file re-parsed on every `_call_llm()` call; no caching | `config.py:281-355` | Unnecessary I/O per LLM iteration |
| PERF-LOW-07 | Rich `Markdown()` rendered synchronously; freezes on large output/history | `console.py:283,335,377` | UI freeze on large responses |

---

## Critical Issues for Phase 3 Context

### Testing Requirements from Security Findings:
1. **SEC-CRIT-01**: Need tests verifying `write_env_value` handles `#` in values correctly
2. **SEC-CRIT-03**: Need tests verifying path traversal rejection in profile loading
3. **SEC-HIGH-03**: Need tests verifying API key masking for various key lengths
4. **SEC-HIGH-05**: Need tests verifying HTTPS enforcement warnings

### Testing Requirements from Performance Findings:
1. **PERF-HIGH-01**: Need tests verifying message list pruning/windowing
2. **PERF-MED-02**: Need tests verifying session save doesn't block excessively
3. **PERF-MED-01**: Need tests verifying ThreadPoolExecutor cleanup

### Documentation Requirements:
1. Security considerations section needed in docs
2. Configuration precedence chain needs clear documentation
3. API key storage security implications should be documented
4. Thread pool lifecycle should be documented for developers

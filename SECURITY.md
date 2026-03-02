# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in GOrchestrator, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

### How to Report

1. Email: Send details to the project maintainer privately
2. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- Acknowledgment within 48 hours
- Status update within 7 days
- Fix timeline depends on severity

### Scope

The following are in scope for security reports:

- **API key handling**: Leakage, improper storage, insufficient masking
- **Path traversal**: Profile loading, file operations
- **Command injection**: Worker subprocess execution
- **Input validation**: User-supplied model names, profile names, configuration values
- **Session data**: Sensitive information in session history files
- **Dependency vulnerabilities**: Known CVEs in dependencies

### Security Architecture

GOrchestrator handles sensitive data including:

- LLM API keys (stored in `.env` and YAML profiles)
- Subprocess execution (Worker agents run shell commands)
- Session history (may contain API responses)

Key security measures in place:

- API keys displayed as `****...{last4}` format
- `yaml.safe_load()` used consistently (no deserialization attacks)
- List-based subprocess arguments (no `shell=True`)
- Profile name validation (path traversal prevention)
- API key masking in error logs and session exports
- Environment variable allowlisting for worker subprocesses
- `.env` files in `.gitignore`

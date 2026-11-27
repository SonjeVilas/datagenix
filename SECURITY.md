# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in **Datagenix** (such as credential exposure, path traversal bypass, command injection, or unsafe agent behavior), **please do not report it through public GitHub issues.**

Instead, please report it privately using GitHub Security Advisories:

- 👉 **[Open a Private Security Advisory](https://github.com/SonjeVilas/datagenix/security/advisories/new)**

Please include:
- A clear description of the vulnerability and affected files/components
- Steps to reproduce or proof-of-concept
- Potential impact and any suggested remediation

We will acknowledge receipt and work with you to verify and address the issue before public disclosure.

---

## Security Practices in Datagenix

- **No Hardcoded Secrets**: Gemini API keys and Snowflake credentials are loaded from environment variables (`.env`) via Pydantic `SecretStr` and masked in logs.
- **Path-Traversal Sandboxing**: `backend/file_manager.py` resolves and enforces write boundaries strictly within configured output directories.
- **Subprocess Safety**: `integrations/dbt_runner.py` and `backend/executor.py` invoke external tools using explicit argument arrays (`shell=False`) and enforce timeouts.
- **Production Safeguards**: Automated runs block `prod` / `production` targets and require explicit approval before executing warehouse-mutating dbt commands.
- **Contributor Reminder**: Always inspect `git diff` before committing to ensure `.env`, real account identifiers, passwords, or API keys are never included.

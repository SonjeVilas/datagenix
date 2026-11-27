# Contributing to Datagenix

Thank you for your interest in contributing to **Datagenix**! Whether you are fixing a bug, improving an AI agent prompt, enhancing the Streamlit dashboard, or adding tests and documentation, your contributions are welcome.

---

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

---

## Getting Started

### 1. Fork & Clone

1. Fork the repository on GitHub (`SonjeVilas/datagenix`).
2. Clone your fork locally (or clone directly if you are a repository collaborator):
   ```bash
   git clone https://github.com/<your-username>/datagenix.git
   cd datagenix
   ```
3. Add the upstream remote so you can stay synced:
   ```bash
   git remote add upstream https://github.com/SonjeVilas/datagenix.git
   ```

### 2. Local Environment Setup

Requires **Python 3.11+**.

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

> **Offline Testing:** You do **not** need live Gemini API keys or Snowflake credentials to run the test suite.

### 3. Run the Test Suite

Always run the unit tests before making and after finishing your changes:

```bash
pytest tests/ -v
```

---

## Development Workflow

1. Create a descriptive branch off `main`:
   ```bash
   git checkout -b feat/your-feature-name
   # or: fix/short-bug-description, docs/what-changed
   ```
2. Keep changes focused and clean:
   - Follow existing type annotations, docstrings, and module layout (`agents/`, `backend/`, `config/`, `frontend/`, `integrations/`, `prompts/`).
   - Add or update unit tests in `tests/` for any new functionality or bug fixes (mock external Gemini/Snowflake calls in tests).
   - Never commit `.env`, API keys, database passwords, or generated `profiles.yml` files with credentials.
3. Run verification checks locally:
   ```bash
   pytest tests/ -v
   ```
4. Commit with clear commit messages (Conventional Commits recommended: `feat:`, `fix:`, `docs:`, `test:`, `chore:`):
   ```bash
   git commit -m "feat(agents): improve SQL schema edge-case handling"
   ```
5. Push your branch and open a Pull Request against `main`:
   ```bash
   git push origin feat/your-feature-name
   ```

---

## What Happens in CI on Your PR

- **Python Unit Tests**: Automatically runs `pytest tests/ -v` on every PR modifying application code or tests.
- **SQLFluff Lint**: Lints SQL models inside `generated_projects/**`.
- **dbt Validation**: Validates and parses dbt projects. *(Live Snowflake `dbt build` runs automatically when repository Snowflake secrets are available; forked PRs run offline `dbt parse` validation without requiring warehouse secrets.)*

---

## Reporting Bugs or Suggesting Features

- Use the [Issue Templates](https://github.com/SonjeVilas/datagenix/issues/new/choose) to report bugs or propose enhancements.
- For security vulnerabilities, please follow [SECURITY.md](SECURITY.md) rather than opening a public issue.

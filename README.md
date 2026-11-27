# 🏭 Datagenix – Multi-Agent AI dbt Engineering Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini%20API-4285F4.svg)](https://ai.google.dev/)
[![dbt Core](https://img.shields.io/badge/data--transform-dbt--core%20%7C%20Snowflake-FF694B.svg)](https://www.getdbt.com/)
[![Tests](https://img.shields.io/badge/tests-pytest%20passing-green.svg)](https://pytest.org/)

**Datagenix** is an open-source, locally runnable multi-agent AI platform that autonomously designs, builds, validates, and packages production-ready **dbt (data build tool)** projects for **Snowflake** from natural-language business requirements.

Powered by **Google Gemini** models (with automatic multi-model fallback) and orchestrated via **LangGraph**, Datagenix employs 11 specialized AI agents that analyze requirements, discover source schemas, architect dimensional layers, write modular Snowflake SQL CTEs, generate YAML configs & tests, perform static/AST validation, self-heal errors, and package ready-to-deploy dbt repositories.

---

## 🌟 Key Capabilities

- **Autonomous Multi-Agent Workflow**: 11 dedicated AI agents operating with structured system prompts and Pydantic-validated JSON contracts.
- **Dimensional dbt Architecture**: Standardizes projects into **Staging** (`stg_`), **Intermediate** (`int_`), and **Marts** (`dim_`, `fct_`) layers following dbt and Snowflake best practices.
- **Snowflake-Native SQL Generation**: Employs clean CTE structures, `source()` / `ref()` macros, incremental merge/append strategies, and window functions grounded in discovered schemas.
- **Automated Quality Testing**: Generates schema tests (`unique`, `not_null`, `relationships`, `accepted_values`) and `dbt-utils` macro tests tailored to actual column semantics.
- **Self-Healing Error Correction**: Detects SQL syntax flaws, broken refs, or circular dependencies via `sqlglot` AST validation and iteratively patches affected files with rollback backups.
- **Resilient Gemini Client**: Automatic fallback across `gemini-3.8-flash` → `gemini-3.5-flash-lite` → `gemini-3.5-flash` on quota exhaustion (`429`) or transient server errors (`503`).
- **Dual Operating Modes**:
  - **Live Snowflake Discovery**: Connects securely to inspect live databases, schemas, tables, and constraints.
  - **Offline / Air-Gapped Mode**: Ingests manual schema metadata via CSV, JSON, or YAML without requiring warehouse credentials.
- **Enterprise Streamlit Frontend**: Dark-themed dashboard with live agent pipeline visualization, interactive project explorer, in-browser SQL/YAML editors, validation center, and ZIP packaging.
- **Built-In CI/CD**: GitHub Actions workflows for Python unit testing, SQLFluff linting, dbt validation, and Snowflake native Git deployment (`CREATE DBT PROJECT` / `EXECUTE DBT PROJECT`).

---

## 🏗️ Architecture & Agent Pipeline

```
                                  [ User Requirements ]
                                            │
                                            ▼
                           ┌─────────────────────────────────┐
                           │   Requirement Analyst Agent     │
                           └────────────────┬────────────────┘
                                            │
                                            ▼
                           ┌─────────────────────────────────┐
                           │      Data Discovery Agent       │
                           │   (Snowflake / Manual Files)    │
                           └────────────────┬────────────────┘
                                            │
                                            ▼
                           ┌─────────────────────────────────┐
                           │      Data Architect Agent       │
                           │  (Staging, Inter, Marts, DAG)   │
                           └────────────────┬────────────────┘
                                            │
                                            ▼
                           ┌─────────────────────────────────┐
                           │     Business Logic Agent        │
                           │ (Joins, Aggs, Dedup, SCD Logic) │
                           └────────────────┬────────────────┘
                                            │
                                            ▼
                           ┌─────────────────────────────────┐
                           │      SQL Developer Agent        │
                           │    (CTEs, ref/source, Dims)     │
                           └────────────────┬────────────────┘
                                            │
                                            ▼
                           ┌─────────────────────────────────┐
                           │      YAML Developer Agent       │
                           │(dbt_project, sources, schemas)  │
                           └────────────────┬────────────────┘
                                            │
                                            ▼
                           ┌─────────────────────────────────┐
                           │       Data Quality Agent        │
                           │  (Generic + dbt-utils tests)    │
                           └────────────────┬────────────────┘
                                            │
                                            ▼
                           ┌─────────────────────────────────┐
                           │      Documentation Agent        │
                           │  (Lineage, Readme, Dictionary)  │
                           └────────────────┬────────────────┘
                                            │
                                            ▼
                           ┌─────────────────────────────────┐
                           │     QA & Validation Agent       │
                           │(AST, sqlglot, ref verification) │
                           └────────────────┬────────────────┘
                                            │
                                ┌───────────┴───────────┐
                       [Issues Found?]             [Clean Pass]
                                │                       │
                                ▼                       │
                    ┌───────────────────────┐           │
                    │ Error Fixer Agent     │           │
                    │ (Self-Healing Loop)   │           │
                    └───────────┬───────────┘           │
                                │ (Re-Validate)         │
                                └───────────┐           │
                                            ▼           ▼
                                   ┌─────────────────────────┐
                                   │ Project Packaging Agent │
                                   │   (Zip & File System)   │
                                   └─────────────────────────┘
```

---

## 🤖 The 11 Specialized AI Agents

| # | Agent Name | Core Responsibility | Output Artifact |
|---|---|---|---|
| 1 | **Requirement Analyst** | Deconstructs natural-language prompts into entities, transformations, and quality rules. | `project_specification.json` |
| 2 | **Data Discovery** | Connects to Snowflake or parses CSV/JSON/YAML to map tables, columns, and data types. | `source_catalog.json` |
| 3 | **Data Architect** | Designs the dbt DAG, directory layers (staging, intermediate, marts), and materializations. | `architecture.json` |
| 4 | **Business Logic** | Translates business rules into join specifications, deduplication, NULL handling, and SCDs. | `business_logic.json` |
| 5 | **SQL Developer** | Writes Snowflake-optimized dbt models utilizing CTEs and Jinja `ref()` / `source()`. | `models/**/*.sql` |
| 6 | **YAML Developer** | Generates `dbt_project.yml`, `sources.yml`, `schema.yml`, `packages.yml`, and `profiles.yml.example`. | `**/*.yml` |
| 7 | **Data Quality** | Generates relevant primary key, foreign key, not-null, and `dbt-utils` assertion tests. | `tests/**/*.sql`, `schema.yml` |
| 8 | **Documentation** | Produces descriptions, column dictionaries, business definitions, and project README. | `models/**/*.md`, `README.md` |
| 9 | **QA & Validation** | Inspects models using `sqlglot`, YAML parsers, circular dependency checkers, and AST rules. | `qa_report.json` |
| 10 | **Error Correction** | Targeted self-healing agent that repairs syntax errors and broken references with backups. | `error_corrections` history |
| 11 | **Project Packaging** | Verifies complete project structure, generates setup guides, requirements, and downloadable ZIP. | Final project directory & `.zip` |

---

## 💻 Tech Stack

- **Orchestration**: `LangGraph` (with `MemorySaver` checkpointing and conditional graph routing)
- **AI Engine**: `google-genai` (Google Gemini 3.8 Flash / 3.5 Flash / 3.5 Flash-Lite with auto-fallback)
- **Data Engineering**: `dbt-core`, `dbt-snowflake`, `snowflake-connector-python`, `sqlglot`, `sqlfluff`
- **Validation & Models**: `pydantic v2`, `pydantic-settings`, `pyyaml`
- **Frontend Dashboard**: `Streamlit` (custom dark CSS layout and responsive UI components)
- **Local Storage**: `SQLite` (project executions, metadata, metrics, and error audit trail)
- **Testing & CI/CD**: `pytest`, GitHub Actions, Snowflake Native Git Integration

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python **3.11+** installed (tested through Python 3.13)
- Windows 10/11, macOS, or Linux
- Google Gemini API Key ([Get one here](https://aistudio.google.com/))
- *(Optional)* Snowflake account credentials

### 2. Installation

Clone the repository and navigate into the project directory:
```bash
git clone https://github.com/SonjeVilas/datagenix.git
cd datagenix
```

Create a virtual environment and install dependencies:
```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configuration

Copy the example environment configuration:
```bash
cp .env.example .env
```

Edit `.env` and provide your Gemini API key:
```ini
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-3.8-flash

# Optional: Snowflake credentials for live discovery and execution
SNOWFLAKE_ACCOUNT=
SNOWFLAKE_USER=
SNOWFLAKE_PASSWORD=
SNOWFLAKE_ROLE=
SNOWFLAKE_WAREHOUSE=
SNOWFLAKE_DATABASE=
SNOWFLAKE_SCHEMA=
```

---

## 🖥️ Running the Application

### Option A: Launch the Streamlit Web Dashboard

```bash
streamlit run app.py
```
Open your browser to `http://localhost:8501`.

The dashboard includes 10 integrated navigation views:
1. **📊 Dashboard**: High-level execution metrics, recent projects, and quick-action shortcuts.
2. **🚀 New Project**: Guided wizard to enter requirements, upload metadata, and trigger agents.
3. **🤖 AI Agents**: Real-time status cards, execution progress bar, and execution logs for each agent.
4. **🗄️ Data Sources**: Snowflake connection tester, schema explorer, and manual metadata uploader.
5. **📁 Project Explorer**: Interactive file tree browser with single-file and full-ZIP download.
6. **📝 SQL Editor**: In-browser SQL viewer with syntax highlighting and `sqlglot` validation.
7. **⚙️ YAML Editor**: In-browser dbt YAML viewer and validator.
8. **🛡️ Validation Center**: AST validation findings, broken ref detection, and self-healing logs.
9. **📜 Execution History**: Comprehensive audit log of past project builds and agent runs.
10. **🔧 Settings**: Live configuration for Gemini API keys, model selection, and Snowflake credentials.

### Option B: Command Line Interface (CLI)

Run the autonomous pipeline directly without starting the UI:

```bash
python main.py --name ecommerce_analytics --requirements "Build customer 360 and order transaction marts with customer deduplication and daily revenue facts."
```

Or pass a requirements file:
```bash
python main.py --name banking_analytics --requirements ./sample_data/requirements.txt --output-dir ./generated_projects
```

---

## 🧪 Running Automated Tests

The unit test suite runs **100% offline** using mocked Gemini responses and requires no live API keys or warehouse credentials:

```bash
pytest tests/ -v
```

All **32 tests** validate:
- Gemini client JSON parsing, retry policies, and model fallback
- Pydantic state serialization & settings secret masking
- `FileManager` path-traversal sandboxing
- SQLite persistence and metrics aggregation
- Static SQL and YAML validation with circular dependency detection
- Agent execution workflows & LangGraph orchestration
- Subprocess safety with argument lists and timeout handling

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for a step-by-step end-to-end walkthrough and [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for Snowflake CI/CD deployment setup.

---

## 🔒 Security & Safe Execution Controls

1. **Strict Path-Traversal Sandbox**: `FileManager` verifies that all file reads and writes resolve strictly within designated output directories, preventing path-traversal attacks (`../../`).
2. **Credential Masking**: API keys and database passwords are encapsulated inside Pydantic `SecretStr` models and masked in log outputs.
3. **No Automatic Production Runs**: Production deployment targets (`prod`, `production`) are hard-blocked from automated execution.
4. **Human-in-the-Loop Warehouse Gates**: Database-affecting commands (`dbt run`, `dbt build`) enforce explicit approval before spawning subprocesses.
5. **Subprocess Argument Lists**: CLI operations use argument lists (`subprocess.run(["dbt", ...])`) with `shell=False` to prevent command injection.

See [SECURITY.md](SECURITY.md) for vulnerability reporting guidelines.

---

## 🤝 Contributing

We welcome open-source contributions! Whether it's bug fixes, new dbt pattern templates, prompt engineering improvements, or additional data platform integrations:

1. Check open [Issues](https://github.com/SonjeVilas/datagenix/issues) or open a new feature request / bug report.
2. Read [CONTRIBUTING.md](CONTRIBUTING.md) and our [Code of Conduct](CODE_OF_CONDUCT.md).
3. Fork the repository, create a feature branch, ensure `pytest tests/ -v` passes, and open a Pull Request!

---

## 📄 License

Licensed under the [MIT License](LICENSE). Built for the open-source data engineering community.

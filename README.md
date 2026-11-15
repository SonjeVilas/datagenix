# 🏭 dbt Project Factory – Multi-Agent AI Data Engineering Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini%20API-4285F4.svg)](https://ai.google.dev/)
[![dbt Core](https://img.shields.io/badge/data--transform-dbt--core%20%7C%20Snowflake-FF694B.svg)](https://www.getdbt.com/)
[![Tests](https://img.shields.io/badge/tests-pytest%20passing-green.svg)](https://pytest.org/)

An enterprise-grade, locally runnable AI system that autonomously creates complete, production-ready **dbt (data build tool)** projects for **Snowflake** from natural-language business requirements.

Powered by **Google Gemini** models and orchestrated via **LangGraph**, the system employs a team of 11 specialized AI agents that analyze requirements, discover source structures, design dimensional architectures, generate modular SQL CTEs, configure YAML schemas & sources, implement robust data quality tests, perform static/AST validation, and self-heal errors before packaging.

---

## 🌟 Key Capabilities

- **Autonomous Multi-Agent Workflow**: 11 dedicated AI agents operating with distinct system prompts and Pydantic-validated JSON contracts.
- **Dimensional dbt Architecture**: Standardizes projects into **Staging** (`stg_`), **Intermediate** (`int_`), and **Marts** (`dim_`, `fct_`) layers following dbt and Snowflake best practices.
- **Snowflake-Native SQL Generation**: Employs CTE structures, `source()` / `ref()` macros, incremental merge/append patterns, and window functions without hallucinated columns.
- **Automated Quality Testing**: Generates schema tests (`unique`, `not_null`, `relationships`, `accepted_values`) and `dbt-utils` macro tests tailored to actual column semantics.
- **Self-Healing Error Correction**: Detects syntax flaws, broken refs, or circular dependencies through static AST validation and iteratively patches affected files with rollback backups (up to configurable retry limits).
- **Dual Operating Modes**:
  - **Live Snowflake Discovery**: Connects securely to discover live databases, schemas, tables, and constraints.
  - **Offline / Air-Gapped Mode**: Ingests manual schema metadata via CSV, JSON, or YAML without requiring warehouse credentials.
- **Enterprise Streamlit Frontend**: Dark-themed dashboard with live agent workflow visualization, visual project directory tree, in-browser SQL/YAML editors, validation center, and ZIP packaging.
- **Security by Design**: Path-traversal sandboxing, secret masking in logs, read-only discovery, and human-in-the-loop approval gates before any warehouse execution.

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
| 6 | **YAML Developer** | Generates `dbt_project.yml`, `sources.yml`, `schema.yml`, and `profiles.yml.example`. | `**/*.yml` |
| 7 | **Data Quality** | Generates relevant primary key, foreign key, not-null, and `dbt-utils` assertion tests. | `tests/**/*.sql`, `schema.yml` |
| 8 | **Documentation** | Produces descriptions, column dictionaries, business definitions, and project README. | `models/**/*.md`, `README.md` |
| 9 | **QA & Validation** | Inspects models using `sqlglot`, YAML parsers, circular dependency checkers, and AST rules. | `qa_report.json` |
| 10 | **Error Correction** | Targeted self-healing agent that repairs syntax errors and broken references with backups. | `error_corrections` history |
| 11 | **Project Packaging** | Verifies complete project structure, generates setup guides, requirements, and downloadable ZIP. | Final project directory & `.zip` |

---

## 💻 Tech Stack

- **Orchestration**: `LangGraph` (with `MemorySaver` checkpointing and conditional graph routing)
- **AI Engine**: `google-genai` (Google Gemini 2.0 Flash / Pro)
- **Data Engineering**: `dbt-core`, `dbt-snowflake`, `snowflake-connector-python`, `sqlglot`, `sqlfluff`
- **Validation & Models**: `pydantic v2`, `pydantic-settings`, `pyyaml`
- **Frontend Dashboard**: `Streamlit` (with custom CSS layout and responsive UI components)
- **Local Storage**: `SQLite` (project executions, metadata, metrics, and error audit trail)
- **Testing**: `pytest`

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python **3.11+** installed (tested on Python 3.13)
- Windows 10/11, macOS, or Linux
- Google Gemini API Key ([Get one here](https://aistudio.google.com/))
- *(Optional)* Snowflake account credentials

### 2. Installation

Clone or navigate to the repository directory:
```bash
cd "d:\AI-Powered Multi-Agent dbt Project Factory"
```

Install required dependencies:
```bash
pip install -r requirements.txt
```

### 3. Configuration

Copy the example environment configuration:
```bash
cp .env.example .env
```

Edit `.env` and provide your Gemini API key:
```ini
GEMINI_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash

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
python main.py --name banking_analytics --requirements ./requirements_doc.txt --output-dir ./generated_projects
```

---

## 🧪 Running Automated Tests

The test suite runs 100% offline using mocked Gemini responses and requires no live credentials or API credits:

```bash
pytest tests/ -v
```

All 29 tests validate:
- Gemini client JSON parsing and retry policies
- Pydantic state serialization
- FileManager path-traversal sandboxing
- SQLite persistence and metrics aggregation
- Static SQL and YAML validation with circular dependency detection
- Agent execution workflows
- Subprocess safety with argument lists and timeout handling

---

## 🔒 Security & Safe Execution Controls

1. **Strict Path-Traversal Sandbox**: The `FileManager` verifies that all file reads and writes resolve strictly within designated output directories, preventing path-traversal attacks (`../../`).
2. **Credential Masking**: API keys and database passwords are encapsulated inside Pydantic `SecretStr` models and automatically masked in log outputs.
3. **No Automatic Production Runs**: Production deployment targets (`prod`, `production`) are hard-blocked from automated execution.
4. **Human-in-the-Loop Warehouse Gates**: Database-affecting commands (`dbt run`, `dbt build`) enforce explicit human approval before any subprocess is spawned.
5. **Subprocess Argument Lists**: All CLI operations use argument lists (`subprocess.run(["dbt", ...])`) instead of `shell=True` to eliminate shell injection vulnerabilities.

---

## 📄 License

MIT License. Designed and engineered for high-velocity data engineering teams.


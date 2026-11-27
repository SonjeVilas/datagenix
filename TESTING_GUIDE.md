# 🧪 Datagenix – Complete End-to-End Testing & Setup Guide

A step-by-step setup and testing manual for **Datagenix – Multi-Agent AI dbt Engineering Platform**.

Even if you have never worked with dbt, LangGraph, or Streamlit before, this document covers **every command, configuration, and verification step** required to set up, test, and run the complete application locally.

---

## 📋 Table of Contents
1. [System Prerequisites](#1-system-prerequisites)
2. [Environment Setup & Installation](#2-environment-setup--installation)
3. [Configuration & Credentials Setup](#3-configuration--credentials-setup)
   - [Google Gemini API Key](#a-google-gemini-api-key)
   - [Snowflake Data Warehouse](#b-snowflake-data-warehouse)
4. [Step 1: Automated Offline Test Suite](#4-step-1-automated-offline-test-suite)
5. [Step 2: Starting the Streamlit Web Application](#5-step-2-starting-the-streamlit-web-application)
6. [Step 3: Verifying Connectivity in Settings](#6-step-3-verifying-connectivity-in-settings)
7. [Step 4: Live Data Discovery in Snowflake](#7-step-4-live-data-discovery-in-snowflake)
8. [Step 5: End-to-End dbt Project Generation Test](#8-step-5-end-to-end-dbt-project-generation-test)
9. [Step 6: Inspecting the Generated dbt Artifacts](#9-step-6-inspecting-the-generated-dbt-artifacts)
10. [Step 7: Validating and Downloading the Project ZIP](#10-step-7-validating-and-downloading-the-project-zip)
11. [Troubleshooting & Frequently Encountered Errors](#11-troubleshooting--frequently-encountered-errors)

---

## 1. System Prerequisites

Before running the app, ensure you have:
- **Operating System**: Windows 10/11, macOS, or Linux.
- **Python**: Version **3.11, 3.12, or 3.13** installed and available on your `PATH`.
- **Web Browser**: Chrome, Edge, Firefox, or Safari.

Verify your Python version:
```bash
python --version
```

---

## 2. Environment Setup & Installation

### Step 2.1: Clone and Navigate to the Repository
```bash
git clone https://github.com/SonjeVilas/datagenix.git
cd datagenix
```

### Step 2.2: Create and Activate the Virtual Environment
```bash
python -m venv .venv
```

Activate the virtual environment:
```powershell
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
```
```bash
# macOS / Linux:
source .venv/bin/activate
```

### Step 2.3: Install Dependencies
```bash
pip install -r requirements.txt
```
This installs `streamlit`, `google-genai`, `langgraph`, `snowflake-connector-python`, `dbt-core`, `dbt-snowflake`, `sqlglot`, `sqlfluff`, and `pytest`.

---

## 3. Configuration & Credentials Setup

Datagenix reads configuration from a `.env` file in the project root (copied from `.env.example`).

### A. Google Gemini API Key
1. Get a free API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
2. The default model is **`gemini-3.8-flash`** (with automatic fallback to `gemini-3.5-flash-lite` and `gemini-3.5-flash`).

### B. Snowflake Data Warehouse *(Optional)*
You can test Datagenix completely offline using `sample_data/metadata_schema.csv`, or use Snowflake with sample tables (`sample_data/snowflake_sample_insert.sql`):

```sql
-- 1. Create dedicated database and schema
CREATE DATABASE IF NOT EXISTS ECOM_DB;
CREATE SCHEMA IF NOT EXISTS ECOM_DB.RAW;

-- 2. Create raw source tables (see also sample_data/snowflake_sample_insert.sql)
CREATE OR REPLACE TABLE ECOM_DB.RAW.CUSTOMERS (
    CUSTOMER_ID NUMBER(38,0),
    FIRST_NAME VARCHAR(100),
    LAST_NAME VARCHAR(100),
    EMAIL VARCHAR(255),
    CREATED_AT TIMESTAMP_NTZ(9)
);

CREATE OR REPLACE TABLE ECOM_DB.RAW.ORDERS (
    ORDER_ID NUMBER(38,0),
    CUSTOMER_ID NUMBER(38,0),
    ORDER_DATE DATE,
    STATUS VARCHAR(50),
    TOTAL_AMOUNT NUMBER(10,2)
);

CREATE OR REPLACE TABLE ECOM_DB.RAW.ORDER_ITEMS (
    ITEM_ID NUMBER(38,0),
    ORDER_ID NUMBER(38,0),
    PRODUCT_ID NUMBER(38,0),
    QUANTITY NUMBER(38,0),
    UNIT_PRICE NUMBER(10,2)
);

-- 3. Optional: Create a dedicated service user
CREATE USER IF NOT EXISTS DBT_USER
    PASSWORD = 'YourSecurePassword@123'
    DEFAULT_ROLE = 'ACCOUNTADMIN'
    MUST_CHANGE_PASSWORD = FALSE;

GRANT ROLE ACCOUNTADMIN TO USER DBT_USER;
```

### C. Populate `.env`
Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-3.8-flash
SNOWFLAKE_ACCOUNT=YOUR_ORG-YOUR_ACCOUNT
SNOWFLAKE_USER=DBT_USER
SNOWFLAKE_PASSWORD=YourSecurePassword@123
SNOWFLAKE_ROLE=ACCOUNTADMIN
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=ECOM_DB
SNOWFLAKE_SCHEMA=RAW
PROJECT_OUTPUT_DIR=generated_projects
MAX_RETRIES=3
LOG_LEVEL=INFO
```

---

## 4. Step 1: Automated Offline Test Suite

Verify that all core modules pass automated unit and integration tests (**100% offline** using mocked AI responses and temporary sandboxes):

```bash
pytest tests/ -v
```

### ✅ Expected Result:
```text
============================= 32 passed in ~4s =============================
```

---

## 5. Step 2: Starting the Streamlit Web Application

```bash
streamlit run app.py
```

Open your browser to **[http://localhost:8501](http://localhost:8501)**.

---

## 6. Step 3: Verifying Connectivity in Settings

1. In the left sidebar, click **🔧 Settings**.
2. **Gemini Test**: Click **🤖 Test Gemini Connection** and verify the green confirmation banner.
3. **Snowflake Test** *(if configured)*: Verify connection details and click **❄️ Test Snowflake Connection**.

---

## 7. Step 4: Live Data Discovery in Snowflake

1. In the sidebar, click **🗄️ Data Sources**.
2. Inspect the discovered tables (`CUSTOMERS`, `ORDERS`, `ORDER_ITEMS`) and column schemas—or upload `sample_data/metadata_schema.csv` in offline mode.

---

## 8. Step 5: End-to-End dbt Project Generation Test

1. In the sidebar, click **🚀 New Project**.
2. Enter:
   - **Project Name**: `ecom_analytics`
   - **Project Description**: `E-Commerce Dimensional Marts`
   - **Business Requirements**:
     ```text
     Build a dimensional dbt project for our e-commerce data warehouse in Snowflake.

     Source tables in ECOM_DB.RAW:
     1. CUSTOMERS (customer_id, first_name, last_name, email, created_at)
     2. ORDERS (order_id, customer_id, order_date, status, total_amount)
     3. ORDER_ITEMS (item_id, order_id, product_id, quantity, unit_price)

     Requirements:
     - Staging Layer:
       - stg_customers: clean email, standardize names, cast dates.
       - stg_orders: normalize status, cast amounts.
       - stg_order_items: calculate item_total = quantity * unit_price.
     - Intermediate Layer:
       - int_customer_order_summary: calculate customer lifetime value, total orders, first/last order date.
     - Marts Layer:
       - dim_customers: enriched customer dimension with order metrics.
       - fct_orders: order transaction fact model with incremental merge strategy keyed on order_id.
     - Testing & Quality:
       - unique and not_null tests on primary keys.
       - relationship integrity test between orders.customer_id and customers.customer_id.
     ```
3. Choose **Enable Snowflake Connection** (or upload manual metadata CSV).
4. Click **🤖 Analyze Requirements & Generate Project**.

---

## 9. Step 6: Inspecting the Generated dbt Artifacts

Monitor the 11 LangGraph agents on the **🤖 AI Agents** page:

| Agent | Responsibility | Artifact Produced |
| :--- | :--- | :--- |
| **1. Requirement Analyst** | Parses entities, grains, and business rules | `project_specification.json` |
| **2. Data Discovery** | Inspects Snowflake or uploaded metadata | `source_catalog.json` |
| **3. Data Architect** | Designs staging, intermediate, and marts layers | `architecture.json` |
| **4. Business Logic** | Formulates joins, window functions, and deduplication | `business_logic.json` |
| **5. SQL Developer** | Writes Snowflake SQL models with CTEs, `source()`, `ref()` | `models/**/*.sql` |
| **6. YAML Developer** | Generates dbt configurations and schema tests | `dbt_project.yml`, `sources.yml`, `schema.yml` |
| **7. Data Quality** | Adds generic (`unique`, `not_null`) and `dbt-utils` tests | Schema test configurations |
| **8. Documentation** | Adds model and column documentation | `README.md`, lineage docs |
| **9. QA & Validation** | Validates SQLGlot AST syntax, refs, and DAG cycles | `qa_report.json` |
| **10. Error Correction** | Self-heals syntax flaws or broken references | Backup & patch history |
| **11. Packaging** | Bundles the project directory and creates `.zip` archive | `ecom_analytics.zip` |

---

## 10. Step 7: Validating and Downloading the Project ZIP

1. **📁 Project Explorer**: Browse generated models, YAML files, docs, and download the ZIP.
2. **📝 SQL Editor / ⚙️ YAML Editor**: Inspect and edit SQL and YAML definitions in-browser.
3. **🛡️ Validation Center**: Verify 0 AST/graph validation errors.

---

## 11. Troubleshooting & Frequently Encountered Errors

### 1. `Incorrect username or password was specified` in Snowflake
- **Cause**: Using an email instead of the Snowflake user login name, or an SSO user without a local SQL password.
- **Fix**: Create/use a SQL password service user in Snowflake and enter its `username` in Settings.

### 2. Gemini Rate Limit / `429` or `503` Errors
- **Behavior**: `GeminiClient` automatically falls back across `gemini-3.8-flash` → `gemini-3.5-flash-lite` → `gemini-3.5-flash`. If all models exhaust daily free-tier limits, wait for quota reset or use a billed Google AI Studio API key.

### 3. Streamlit port in use (`address already in use :::8501`)
- **Fix**: Run Streamlit on a different port:
  ```bash
  streamlit run app.py --server.port 8502
  ```

---
*Testing Guide for Datagenix – Multi-Agent AI dbt Engineering Platform.*

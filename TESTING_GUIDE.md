# 🧪 dbt Project Factory – Complete End-to-End Testing & Setup Guide

A beginner-friendly, step-by-step testing manual for **dbt Project Factory – Multi-Agent AI Data Engineering Platform**. 

Even if you have never worked with dbt, LangGraph, or Streamlit before, this document covers **every single command, click, and verification step** required to set up, test, and run the complete application.

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
- **Operating System**: Windows 10/11 (or macOS / Linux).
- **Python**: Version **3.11, 3.12, or 3.13** installed and added to your system `PATH`.
- **PowerShell / Terminal**: Available out of the box on Windows.
- **Web Browser**: Chrome, Edge, Firefox, or Safari.

To check your Python version, open Windows PowerShell and type:
```powershell
python --version
```
*(If it displays `Python 3.11.x`, `3.12.x`, or `3.13.x`, you are ready).*

---

## 2. Environment Setup & Installation

### Step 2.1: Open PowerShell in Project Directory
Navigate into the root folder:
```powershell
cd "d:\AI-Powered Multi-Agent dbt Project Factory"
```

### Step 2.2: Create and Activate the Virtual Environment
Create an isolated Python environment called `.venv`:
```powershell
python -m venv .venv
```

Activate the virtual environment:
```powershell
.\.venv\Scripts\Activate.ps1
```
*(You will see `(.venv)` appear on the left of your terminal prompt).*

### Step 2.3: Install Dependencies
Install all required libraries specified in `requirements.txt`:
```powershell
pip install -r requirements.txt
```
This installs:
- `streamlit` (Web UI)
- `google-genai` (Gemini API SDK)
- `langgraph` (Multi-agent graph orchestrator)
- `snowflake-connector-python` (Snowflake data warehouse connector)
- `dbt-core` & `dbt-snowflake` (dbt compilation and testing engines)
- `sqlglot` & `sqlfluff` (SQL parsing & dialect validation)
- `pytest` (Automated testing framework)

---

## 3. Configuration & Credentials Setup

The application reads configuration from a `.env` file in the project root.

### A. Google Gemini API Key
1. Get a free API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
2. The recommended model is **`gemini-3.5-flash`** (verified fast, stable, and active).

### B. Snowflake Data Warehouse
If using a 30-day Snowflake trial:
1. Log in to your [Snowflake Snowsight Console](https://app.snowflake.com/).
2. Open a **SQL Worksheet** (click `+ Create` > `SQL Worksheet`).
3. Paste and run this setup script:

```sql
-- 1. Create dedicated database and schema
CREATE DATABASE IF NOT EXISTS ECOM_DB;
CREATE SCHEMA IF NOT EXISTS ECOM_DB.RAW;

-- 2. Create raw source tables
CREATE OR REPLACE TABLE ECOM_DB.RAW.CUSTOMERS (
    CUSTOMER_ID NUMBER(38,0),
    EMAIL VARCHAR(255),
    FIRST_NAME VARCHAR(100),
    LAST_NAME VARCHAR(100),
    SIGNUP_DATE DATE,
    COUNTRY VARCHAR(50)
);

CREATE OR REPLACE TABLE ECOM_DB.RAW.ORDERS (
    ORDER_ID NUMBER(38,0),
    CUSTOMER_ID NUMBER(38,0),
    ORDER_DATE DATE,
    STATUS VARCHAR(50),
    TOTAL_AMOUNT NUMBER(10,2),
    CURRENCY VARCHAR(10)
);

CREATE OR REPLACE TABLE ECOM_DB.RAW.ORDER_ITEMS (
    ITEM_ID NUMBER(38,0),
    ORDER_ID NUMBER(38,0),
    PRODUCT_ID NUMBER(38,0),
    QUANTITY NUMBER(38,0),
    UNIT_PRICE NUMBER(10,2)
);

-- 3. Create a dedicated user for Python / dbt connections
CREATE USER IF NOT EXISTS DBT_USER 
    PASSWORD = 'YourSecurePassword@123' 
    DEFAULT_ROLE = 'ACCOUNTADMIN'
    MUST_CHANGE_PASSWORD = FALSE;

GRANT ROLE ACCOUNTADMIN TO USER DBT_USER;
```

### C. Populate `.env`
Open `.env` in any text editor and fill in your details:
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash
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

Before opening the browser, verify that all core modules pass automated unit and integration tests. These tests run **100% offline** using mocked AI responses and sandbox databases.

Run in PowerShell:
```powershell
.\.venv\Scripts\pytest.exe tests/ -v
```

### ✅ Expected Result:
```text
============================= 29 passed in 3.17s =============================
```
- Tests all 11 agents (`RequirementAgent`, `DiscoveryAgent`, `ArchitectAgent`, `SQLDeveloperAgent`, `YAMLDeveloperAgent`, `DataQualityAgent`, `DocumentationAgent`, `QAValidationAgent`, `ErrorCorrectionAgent`, `PackagingAgent`).
- Tests SQLite project history persistence.
- Tests path-traversal security sandbox.
- Tests AST SQL validation via SQLGlot.

---

## 5. Step 2: Starting the Streamlit Web Application

Run the application:
```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

### ✅ Expected Output:
```text
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

Open your browser to: **[http://localhost:8501](http://localhost:8501)**.

---

## 6. Step 3: Verifying Connectivity in Settings

1. In the left sidebar of the Streamlit dashboard, click **🔧 Settings**.
2. **Gemini Test**:
   - Verify **Gemini Model** is `gemini-3.5-flash`.
   - Click **🧪 Test Gemini Connection**.
   - ✅ **Expected**: A green banner reading:
     > `✅ Gemini connected successfully using model gemini-3.5-flash!`
3. **Snowflake Test**:
   - Verify your **Account**, **Username** (`DBT_USER`), **Password**, **Database** (`ECOM_DB`), and **Schema** (`RAW`).
   - Click **❄️ Test Snowflake Connection**.
   - ✅ **Expected**: A green banner reading:
     > `✅ Snowflake connection successful!`

---

## 7. Step 4: Live Data Discovery in Snowflake

1. In the sidebar, click **🔍 Data Sources**.
2. You will see:
   - **Discovered Tables**: `CUSTOMERS`, `ORDERS`, `ORDER_ITEMS`.
   - **Column details**: column names, datatypes, and nullability retrieved live from your Snowflake warehouse.
3. This proves that the **Data Discovery Agent** can inspect your schema directly.

---

## 8. Step 5: End-to-End dbt Project Generation Test

1. In the sidebar, click **🚀 New Project**.
2. Fill out the project form:
   - **Step 1: Project Information**:
     - Project Name: `ecom_analytics`
     - Project Description: `E-Commerce Dimensional Marts`
   - **Step 2: Business Requirements**: Paste the following prompt:
     ```text
     Build a dimensional dbt project for our e-commerce data warehouse in Snowflake.

     Source tables in ECOM_DB.RAW:
     1. CUSTOMERS (customer_id, email, first_name, last_name, signup_date, country)
     2. ORDERS (order_id, customer_id, order_date, status, total_amount, currency)
     3. ORDER_ITEMS (item_id, order_id, product_id, quantity, unit_price)

     Requirements:
     - Staging Layer:
       - stg_customers: clean email, concatenate full name, cast dates.
       - stg_orders: filter out test orders, cast amounts.
       - stg_order_items: calculate line_item_total = quantity * unit_price.
     - Intermediate Layer:
       - int_customer_order_summary: calculate customer lifetime value, total orders, first/last order date.
     - Marts Layer:
       - dim_customers: enriched customer dimension with order metrics.
       - fct_orders: daily orders fact model with incremental merge strategy keyed on order_id.
     - Testing & Quality:
       - unique and not_null tests on primary keys.
       - relationship integrity test between orders.customer_id and customers.customer_id.
     ```
   - **Step 3: Source Data**:
     - Toggle **Enable Snowflake Connection** to **ON**.
   - **Step 4: Configuration**:
     - Target Schema: `analytics`
     - Default Materialization: `view`
     - dbt Version Target: `1.7.x`
3. Click the blue button: **🎯 Analyze Requirements & Generate Project**.

---

## 9. Step 6: Inspecting the Generated dbt Artifacts

Watch the 11 specialized LangGraph agents collaborate in real time:

| Agent | Responsibility | Artifact Produced |
| :--- | :--- | :--- |
| **1. Requirement Analyst** | Parses entities, grains, and business rules | `project_specification.json` |
| **2. Data Discovery** | Inspects Snowflake `ECOM_DB.RAW` metadata | `source_catalog.json` |
| **3. Data Architect** | Designs staging, intermediate, and marts layers | `architecture.json` |
| **4. Business Logic** | Formulates joins, window functions, and deduplication | `business_logic.json` |
| **5. SQL Developer** | Writes Snowflake SQL models with CTEs, `source()`, `ref()` | `models/**/*.sql` |
| **6. YAML Developer** | Generates dbt configurations and schema tests | `dbt_project.yml`, `sources.yml`, `schema.yml` |
| **7. Data Quality** | Adds generic (`unique`, `not_null`) and `dbt-utils` tests | Schema test configurations |
| **8. Documentation** | Adds model and column documentation | `README.md`, column definitions |
| **9. QA & Validation** | Validates SQLGlot AST syntax, refs, and DAG cycles | `qa_report.json` |
| **10. Error Correction** | Self-heals any syntax flaws or broken references | Backup & patch files |
| **11. Packaging** | Bundles the project structure and creates `.zip` archive | `ecom_analytics.zip` |

---

## 10. Step 7: Validating and Downloading the Project ZIP

Once the execution completes:

1. **📁 Project Explorer**:
   - Browse the generated folder hierarchy:
     ```text
     generated_projects/ecom_analytics/
     ├── dbt_project.yml
     ├── packages.yml
     ├── requirements.txt
     ├── README.md
     └── models/
         ├── staging/
         │   ├── sources.yml
         │   ├── schema.yml
         │   ├── stg_customers.sql
         │   ├── stg_orders.sql
         │   └── stg_order_items.sql
         ├── intermediate/
         │   ├── schema.yml
         │   └── int_customer_order_summary.sql
         └── marts/
             ├── schema.yml
             ├── dim_customers.sql
             └── fct_orders.sql
     ```
2. **📝 SQL Editor**:
   - Inspect individual SQL models. Notice proper CTE structure (`import`, `transformed`, `final`), snake_case casting, and explicit `{{ ref(...) }}` macros.
3. **📄 YAML Editor**:
   - Verify `schema.yml` contains model descriptions and column tests (`unique`, `not_null`, `relationships`).
4. **🛡️ Validation Center**:
   - View the AST validation summary showing 0 syntax errors.
5. **📦 Download ZIP**:
   - Click **Download Project ZIP** to save `ecom_analytics.zip` to your computer.

---

## 11. Troubleshooting & Frequently Encountered Errors

### 1. `Incorrect username or password was specified` in Snowflake
- **Cause**: Using email address instead of the Snowflake user login name, or using SSO account without a local SQL password.
- **Fix**: Run this in a Snowflake SQL Worksheet:
  ```sql
  CREATE USER IF NOT EXISTS DBT_USER PASSWORD = 'YourPassword123!' DEFAULT_ROLE = 'ACCOUNTADMIN';
  GRANT ROLE ACCOUNTADMIN TO USER DBT_USER;
  ```
  Set Username to `DBT_USER` in Settings.

### 2. `404 NOT_FOUND: models/gemini-2.0-flash is no longer available`
- **Cause**: Older Gemini preview models have been retired by Google.
- **Fix**: Use `gemini-3.5-flash` in Settings (already default in `.env`).

### 3. Streamlit port in use (`address already in use :::8501`)
- **Fix**: Run Streamlit on a different port:
  ```powershell
  .\.venv\Scripts\streamlit.exe run app.py --server.port 8502
  ```

---
*Testing Guide created for dbt Project Factory – Multi-Agent AI Data Engineering Platform.*


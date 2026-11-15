"""
Shared pytest fixtures for the dbt Project Factory test suite.
All tests run WITHOUT real API keys or external connections.
"""
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Mock data – realistic Gemini responses for a "banking analytics" project
# ---------------------------------------------------------------------------

MOCK_PROJECT_SPECIFICATION = {
    "objectives": [
        "Build a dimensional data model for banking analytics",
        "Enable customer 360 view across accounts and transactions",
        "Support regulatory reporting requirements",
    ],
    "source_systems": [
        {"name": "core_banking", "type": "database", "description": "Core transactional system"},
        {"name": "card_processing", "type": "api", "description": "Card transaction feed"},
        {"name": "online_banking", "type": "database", "description": "Web portal database"},
    ],
    "business_entities": [
        {"name": "customer", "description": "Bank account holder", "source_system": "core_banking", "key_columns": ["customer_id"]},
        {"name": "account", "description": "Financial deposit/credit account", "source_system": "core_banking", "key_columns": ["account_id"]},
        {"name": "transaction", "description": "Financial ledger entry", "source_system": "core_banking", "key_columns": ["txn_id"]},
    ],
    "business_rules": [
        {"name": "active_accounts", "description": "Active in 90 days", "logic": "last_txn <= 90 days", "affected_entities": ["account"]},
        {"name": "high_value_customer", "description": "Balance > 100k", "logic": "balance > 100000", "affected_entities": ["customer"]},
    ],
    "transformation_requirements": [
        {"name": "dedup_customers", "description": "Deduplicate customer records", "source_entities": ["customer"], "logic": "dedup by ID", "priority": "high"},
        {"name": "currency_conversion", "description": "Convert currency to USD", "source_entities": ["transaction"], "logic": "multiply daily FX", "priority": "high"},
    ],
    "output_models": [
        {"name": "dim_customer", "description": "Customer dimension", "grain": "customer_id", "key_columns": ["customer_id"], "consumers": ["bi"]},
        {"name": "dim_account", "description": "Account dimension", "grain": "account_id", "key_columns": ["account_id"], "consumers": ["bi"]},
        {"name": "fct_transaction", "description": "Transaction fact", "grain": "txn_id", "key_columns": ["txn_id"], "consumers": ["bi"]},
    ],
    "incremental_requirements": [
        {"entity": "fct_transaction", "strategy": "append", "timestamp_column": "txn_date", "unique_key": "txn_id"},
    ],
    "data_quality_requirements": [
        {"entity": "customer", "rule_type": "not_null", "column": "customer_id", "description": "PK not null", "severity": "error"},
        {"entity": "transaction", "rule_type": "not_null", "column": "amount", "description": "amount not null", "severity": "error"},
    ],
    "assumptions": [
        "Source data is loaded daily via ELT into raw schema",
    ],
    "clarification_questions": [],
}

MOCK_SOURCE_CATALOG = {
    "sources": [
        {
            "name": "core_banking",
            "schema": "raw_banking",
            "tables": [
                {
                    "name": "customers",
                    "columns": [
                        {"name": "customer_id", "type": "VARCHAR", "nullable": False},
                        {"name": "first_name", "type": "VARCHAR", "nullable": True},
                        {"name": "last_name", "type": "VARCHAR", "nullable": True},
                        {"name": "email", "type": "VARCHAR", "nullable": True},
                        {"name": "created_at", "type": "TIMESTAMP", "nullable": False},
                    ],
                },
                {
                    "name": "accounts",
                    "columns": [
                        {"name": "account_id", "type": "VARCHAR", "nullable": False},
                        {"name": "customer_id", "type": "VARCHAR", "nullable": False},
                        {"name": "account_type", "type": "VARCHAR", "nullable": False},
                        {"name": "balance", "type": "NUMBER", "nullable": False},
                        {"name": "opened_at", "type": "DATE", "nullable": False},
                        {"name": "status", "type": "VARCHAR", "nullable": False},
                    ],
                },
                {
                    "name": "transactions",
                    "columns": [
                        {"name": "txn_id", "type": "VARCHAR", "nullable": False},
                        {"name": "account_id", "type": "VARCHAR", "nullable": False},
                        {"name": "txn_type", "type": "VARCHAR", "nullable": False},
                        {"name": "amount", "type": "NUMBER", "nullable": False},
                        {"name": "currency", "type": "VARCHAR", "nullable": False},
                        {"name": "txn_date", "type": "TIMESTAMP", "nullable": False},
                    ],
                },
            ],
        }
    ]
}

MOCK_ARCHITECTURE = {
    "layers": [
        {
            "name": "staging",
            "description": "1:1 source mirrors with light cleaning",
            "directory": "models/staging",
            "schema_prefix": "staging",
            "default_materialization": "view",
            "models": [
                {"name": "stg_core_banking__customers", "layer": "staging", "materialization": "view"},
                {"name": "stg_core_banking__accounts", "layer": "staging", "materialization": "view"},
            ],
        },
        {
            "name": "marts",
            "description": "Final dimensional models for analytics",
            "directory": "models/marts",
            "schema_prefix": "marts",
            "default_materialization": "table",
            "models": [
                {"name": "dim_customer", "layer": "marts", "materialization": "table"},
            ],
        },
    ],
    "models": [
        {"name": "stg_core_banking__customers", "layer": "staging", "materialization": "view"},
        {"name": "stg_core_banking__accounts", "layer": "staging", "materialization": "view"},
        {"name": "dim_customer", "layer": "marts", "materialization": "table"},
    ],
    "dag_edges": [],
    "naming_conventions": {
        "staging": "stg_{source}__{table}",
        "intermediate": "int_{description}",
        "marts": "dim_{entity} or fct_{event}",
    },
    "materialization_strategy": {
        "staging": "view",
        "intermediate": "ephemeral",
        "marts": "table",
    },
    "design_decisions": ["Star schema"],
}

MOCK_BUSINESS_LOGIC = {
    "transformations": [
        {
            "model": "int_customer_accounts",
            "logic": "Join customers to accounts, deduplicate by customer_id keeping most recent",
            "dependencies": ["stg_core_banking__customers", "stg_core_banking__accounts"],
        },
        {
            "model": "fct_transaction",
            "logic": "Convert amounts to USD, add running balance",
            "dependencies": ["stg_core_banking__transactions", "int_customer_accounts"],
        },
    ]
}

MOCK_SQL_MODELS = {
    "models/staging/stg_core_banking__customers.sql": (
        "with source as (\n"
        "    select * from {{ source('core_banking', 'customers') }}\n"
        "),\n"
        "renamed as (\n"
        "    select\n"
        "        customer_id,\n"
        "        trim(lower(first_name)) as first_name,\n"
        "        trim(lower(last_name)) as last_name,\n"
        "        lower(email) as email,\n"
        "        created_at\n"
        "    from source\n"
        ")\n"
        "select * from renamed"
    ),
    "models/staging/stg_core_banking__accounts.sql": (
        "with source as (\n"
        "    select * from {{ source('core_banking', 'accounts') }}\n"
        "),\n"
        "renamed as (\n"
        "    select\n"
        "        account_id,\n"
        "        customer_id,\n"
        "        account_type,\n"
        "        balance,\n"
        "        opened_at,\n"
        "        status\n"
        "    from source\n"
        ")\n"
        "select * from renamed"
    ),
    "models/marts/dim_customer.sql": (
        "with customers as (\n"
        "    select * from {{ ref('stg_core_banking__customers') }}\n"
        "),\n"
        "accounts as (\n"
        "    select * from {{ ref('stg_core_banking__accounts') }}\n"
        "),\n"
        "final as (\n"
        "    select\n"
        "        c.customer_id,\n"
        "        c.first_name,\n"
        "        c.last_name,\n"
        "        c.email,\n"
        "        count(a.account_id) as total_accounts,\n"
        "        sum(a.balance) as total_balance,\n"
        "        c.created_at\n"
        "    from customers c\n"
        "    left join accounts a on c.customer_id = a.customer_id\n"
        "    group by c.customer_id, c.first_name, c.last_name, c.email, c.created_at\n"
        ")\n"
        "select * from final"
    ),
}

MOCK_YAML_MODELS = {
    "models/staging/_stg_core_banking.yml": (
        "version: 2\n\n"
        "models:\n"
        "  - name: stg_core_banking__customers\n"
        "    description: Cleaned customer records from core banking\n"
        "    columns:\n"
        "      - name: customer_id\n"
        "        description: Primary key\n"
        "        tests:\n"
        "          - not_null\n"
        "          - unique\n"
    ),
    "models/staging/_stg_core_banking_sources.yml": (
        "version: 2\n\n"
        "sources:\n"
        "  - name: core_banking\n"
        "    schema: raw_banking\n"
        "    tables:\n"
        "      - name: customers\n"
        "      - name: accounts\n"
        "      - name: transactions\n"
    ),
}

MOCK_QA_REPORT = {
    "overall_status": "pass",
    "checks": [
        {"name": "sql_syntax", "status": "pass", "details": "All SQL files parse correctly"},
        {"name": "yaml_valid", "status": "pass", "details": "All YAML files are valid"},
        {"name": "ref_integrity", "status": "pass", "details": "All refs resolve to existing models"},
        {"name": "naming_convention", "status": "pass", "details": "All models follow naming conventions"},
    ],
    "warnings": [],
    "errors": [],
}

MOCK_QA_REPORT_FAIL = {
    "overall_status": "fail",
    "checks": [
        {"name": "sql_syntax", "status": "pass", "details": "All SQL files parse correctly"},
        {"name": "ref_integrity", "status": "fail", "details": "Model int_foo references non-existent ref('stg_missing')"},
    ],
    "warnings": [],
    "errors": ["Broken ref: stg_missing in int_foo"],
}


# ---------------------------------------------------------------------------
# Helper: minimal ProjectState dict
# ---------------------------------------------------------------------------

def _make_base_state(**overrides) -> Dict[str, Any]:
    """Return a minimal ProjectState-like dict with sensible defaults."""
    state = {
        "project_name": "banking_analytics",
        "project_description": "A dbt project for banking analytics",
        "business_requirements": "Build dimensional models for customer, account, and transaction analytics",
        "project_specification": {},
        "source_catalog": {},
        "architecture": {},
        "business_logic": {},
        "generated_models": {},
        "generated_yaml": {},
        "generated_tests": {},
        "generated_docs": {},
        "qa_report": {},
        "validation_results": {},
        "error_corrections": [],
        "agent_status": {},
        "retry_count": 0,
        "max_retries": 3,
        "current_agent": "",
        "errors": [],
        "warnings": [],
        "human_approval_required": False,
        "snowflake_connected": False,
        "source_metadata_manual": {},
        "project_output_path": "",
        "execution_history": [],
    }
    state.update(overrides)
    return state


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_settings():
    """Return a mock Settings object with safe defaults."""
    settings = MagicMock()
    settings.gemini_api_key = MagicMock()
    settings.gemini_api_key.get_secret_value.return_value = "test-api-key-12345"
    settings.gemini_model = "gemini-3.5-flash"
    settings.snowflake_account = "test_account"
    settings.snowflake_user = "test_user"
    settings.snowflake_password = MagicMock()
    settings.snowflake_password.get_secret_value.return_value = "test-password"
    settings.snowflake_role = "ANALYST"
    settings.snowflake_warehouse = "COMPUTE_WH"
    settings.snowflake_database = "ANALYTICS"
    settings.snowflake_schema = "RAW"
    settings.project_output_dir = "generated_projects"
    settings.max_retries = 3
    settings.log_level = "INFO"
    return settings


@pytest.fixture
def mock_gemini_client():
    """
    Return a MagicMock GeminiClient whose `generate` and `generate_json`
    can be configured per-test to return any response.
    Defaults to returning MOCK_PROJECT_SPECIFICATION.
    """
    client = MagicMock()
    client.generate.return_value = json.dumps(MOCK_PROJECT_SPECIFICATION)
    client.generate_json.return_value = MOCK_PROJECT_SPECIFICATION
    return client


@pytest.fixture
def mock_state():
    """Return a realistic base project state dict."""
    return _make_base_state()


@pytest.fixture
def populated_state():
    """State populated through the happy-path pipeline."""
    return _make_base_state(
        project_specification=MOCK_PROJECT_SPECIFICATION,
        source_catalog=MOCK_SOURCE_CATALOG,
        architecture=MOCK_ARCHITECTURE,
        business_logic=MOCK_BUSINESS_LOGIC,
        generated_models=MOCK_SQL_MODELS,
        generated_yaml=MOCK_YAML_MODELS,
        qa_report=MOCK_QA_REPORT,
    )


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary directory that mimics a dbt project root."""
    project_dir = tmp_path / "banking_analytics"
    project_dir.mkdir()
    (project_dir / "models").mkdir()
    (project_dir / "models" / "staging").mkdir()
    (project_dir / "models" / "intermediate").mkdir()
    (project_dir / "models" / "marts").mkdir()
    (project_dir / "tests").mkdir()
    (project_dir / "macros").mkdir()
    (project_dir / "seeds").mkdir()
    (project_dir / "snapshots").mkdir()
    return project_dir


@pytest.fixture
def mock_snowflake_connection():
    """Return a mock Snowflake connection that simulates query results."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        ("customers", "TABLE", "raw_banking"),
        ("accounts", "TABLE", "raw_banking"),
        ("transactions", "TABLE", "raw_banking"),
    ]
    cursor.description = [
        ("TABLE_NAME",), ("TABLE_TYPE",), ("TABLE_SCHEMA",),
    ]
    conn.cursor.return_value = cursor
    return conn

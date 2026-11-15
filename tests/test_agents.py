"""Unit tests for specialized AI agents using mocked Gemini."""

import json
from unittest.mock import MagicMock, patch
import pytest

from agents import (
    ArchitectAgent,
    DataQualityAgent,
    DiscoveryAgent,
    DocumentationAgent,
    FixerAgent,
    PackagingAgent,
    QAValidationAgent,
    RequirementAgent,
    SQLDeveloperAgent,
    YAMLDeveloperAgent,
)
from tests.conftest import (
    MOCK_ARCHITECTURE,
    MOCK_PROJECT_SPECIFICATION,
    MOCK_QA_REPORT,
    MOCK_SOURCE_CATALOG,
    MOCK_SQL_MODELS,
    MOCK_YAML_MODELS,
)


def test_requirement_agent_execute(mock_state):
    agent = RequirementAgent()
    with patch.object(agent, "_call_gemini_json", return_value=MOCK_PROJECT_SPECIFICATION):
        res_state = agent.execute(mock_state)
        assert "project_specification" in res_state
        assert len(res_state["project_specification"]["objectives"]) > 0
        assert res_state["agent_status"]["requirement_analyst"]["status"] == "completed"


def test_discovery_agent_manual_metadata(mock_state):
    agent = DiscoveryAgent()
    mock_state["source_metadata_manual"] = {
        "customers.csv": "customer_id,name,email\n1,Alice,alice@example.com"
    }
    with patch.object(agent, "_call_gemini_json", return_value=MOCK_SOURCE_CATALOG):
        res_state = agent.execute(mock_state)
        assert "source_catalog" in res_state
        assert res_state["agent_status"]["data_discovery"]["status"] == "completed"


def test_architect_agent_execute(populated_state):
    agent = ArchitectAgent()
    mock_arch_response = {
        "project_name": "banking_analytics",
        "description": "dbt architecture",
        "layers": [
            {
                "name": "staging",
                "directory": "models/staging",
                "models": [
                    {
                        "name": "stg_customers",
                        "layer": "staging",
                        "materialization": "view",
                    }
                ],
            }
        ],
        "dag_edges": [],
    }
    with patch.object(agent, "_call_gemini_json", return_value=mock_arch_response):
        res_state = agent.execute(populated_state)
        assert "architecture" in res_state
        assert res_state["agent_status"]["data_architect"]["status"] == "completed"


def test_sql_agent_execute(populated_state):
    agent = SQLDeveloperAgent()
    mock_sql_response = {
        "models": [
            {
                "file_path": "models/staging/stg_customers.sql",
                "model_name": "stg_customers",
                "sql_content": "select * from {{ source('raw', 'customers') }}",
                "layer": "staging",
                "materialization": "view",
            }
        ],
        "macros": [],
    }
    with patch.object(agent, "_call_gemini_json", return_value=mock_sql_response):
        res_state = agent.execute(populated_state)
        assert "generated_models" in res_state
        assert "models/staging/stg_customers.sql" in res_state["generated_models"]


def test_qa_agent_clean_pass(populated_state):
    agent = QAValidationAgent()
    mock_qa = {
        "status": "passed",
        "score": 100,
        "summary": "All checks passed cleanly",
        "issues": [],
        "metrics": {"total_models": 3},
    }
    with patch.object(agent, "_call_gemini_json", return_value=mock_qa):
        res_state = agent.execute(populated_state)
        assert "qa_report" in res_state
        assert res_state["qa_report"]["status"] == "passed"


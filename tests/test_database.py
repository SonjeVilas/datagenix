"""Unit tests for SQLite database persistence."""

import pytest
from backend.database import Database


def test_database_crud(tmp_path):
    db_file = tmp_path / "test.db"
    db = Database(db_file)

    # Save project
    proj_id = db.save_project(
        project_name="banking",
        description="Banking analytics dbt",
        status="completed",
        output_path="/tmp/banking",
        specification={"objectives": ["dim model"]},
    )
    assert proj_id > 0

    # Get project
    proj = db.get_project("banking")
    assert proj is not None
    assert proj["project_name"] == "banking"
    assert proj["status"] == "completed"

    # List projects
    projs = db.list_projects()
    assert len(projs) == 1

    # Record agent execution
    db.record_agent_execution(
        project_name="banking",
        agent_name="sql_developer",
        status="completed",
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:05Z",
        duration_seconds=5.0,
        summary="Generated 3 models",
    )

    history = db.get_agent_executions("banking")
    assert len(history) == 1
    assert history[0]["agent_name"] == "sql_developer"

    # Record validation
    db.record_validation(
        project_name="banking",
        validation_type="qa_agent",
        passed=True,
        issues=[],
    )

    metrics = db.get_metrics()
    assert metrics["total_projects"] == 1
    assert metrics["successful_validations"] == 1
    assert metrics["total_agent_executions"] == 1


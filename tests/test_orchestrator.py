"""Unit tests for LangGraph Orchestrator and graph compilation."""

from unittest.mock import MagicMock, patch
from backend.database import Database
from backend.orchestrator import Orchestrator, create_graph
from backend.state import ProjectState


def test_orchestrator_initialization(tmp_path):
    db = Database(tmp_path / "test.db")
    orch = Orchestrator(db=db)
    assert orch.graph is not None
    assert orch.db is db


def test_create_graph_factory():
    graph = create_graph()
    assert graph is not None


def test_orchestrator_run_mocked(tmp_path, mock_state):
    db = Database(tmp_path / "test.db")
    orch = Orchestrator(db=db)

    # Mock all agents to succeed and return state directly
    for agent in [
        orch.requirement_agent,
        orch.discovery_agent,
        orch.architect_agent,
        orch.business_logic_agent,
        orch.sql_agent,
        orch.yaml_agent,
        orch.data_quality_agent,
        orch.documentation_agent,
        orch.qa_agent,
        orch.fixer_agent,
        orch.packaging_agent,
    ]:
        def mock_exec(st, a=agent):
            st.setdefault("agent_status", {})[a.name] = {"status": "completed", "message": "OK"}
            if a.name == "qa_validation":
                st["qa_report"] = {"status": "passed", "issues": []}
            return st

        agent.execute = MagicMock(side_effect=mock_exec)

    with patch("time.sleep", return_value=None):
        final_state = orch.run(mock_state)
    assert final_state is not None
    assert "agent_status" in final_state
    assert final_state["agent_status"]["requirement_analyst"]["status"] == "completed"
    assert (
        final_state["agent_status"].get("packaging", {}).get("status") == "completed"
        or final_state["agent_status"].get("project_packaging", {}).get("status") == "completed"
    )


def test_orchestrator_max_retries_termination(tmp_path, mock_state):
    """Verify that when QA validation repeatedly fails, the fixer terminates at max_retries."""
    db = Database(tmp_path / "test.db")
    orch = Orchestrator(db=db)

    for agent in [
        orch.requirement_agent,
        orch.discovery_agent,
        orch.architect_agent,
        orch.business_logic_agent,
        orch.sql_agent,
        orch.yaml_agent,
        orch.data_quality_agent,
        orch.documentation_agent,
        orch.fixer_agent,
        orch.packaging_agent,
    ]:
        def mock_exec(st, a=agent):
            st.setdefault("agent_status", {})[a.name] = {"status": "completed", "message": "OK"}
            return st
        agent.execute = MagicMock(side_effect=mock_exec)

    # QA agent always returns errors to trigger fixer loop
    orch.qa_agent.execute = MagicMock(side_effect=lambda st: {
        **st,
        "qa_report": {
            "status": "failed",
            "issues": [{"severity": "error", "message": "Persistent syntax error"}],
        },
    })

    with patch("time.sleep", return_value=None):
        final_state = orch.run(mock_state)

    assert final_state is not None
    # Fixer should have executed up to max_retries (3) and terminated at packaging
    assert final_state.get("retry_count", 0) >= 3

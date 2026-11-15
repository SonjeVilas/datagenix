"""LangGraph-based multi-agent orchestrator for dbt Project Factory."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Callable, Dict, Generator, List, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agents import (
    ArchitectAgent,
    BusinessLogicAgent,
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
from backend.database import Database
from backend.state import ProjectState

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orchestrates all specialized AI agents via a LangGraph state graph."""

    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or Database()
        self.checkpointer = MemorySaver()

        # Initialize agents
        self.requirement_agent = RequirementAgent()
        self.discovery_agent = DiscoveryAgent()
        self.architect_agent = ArchitectAgent()
        self.business_logic_agent = BusinessLogicAgent()
        self.sql_agent = SQLDeveloperAgent()
        self.yaml_agent = YAMLDeveloperAgent()
        self.data_quality_agent = DataQualityAgent()
        self.documentation_agent = DocumentationAgent()
        self.qa_agent = QAValidationAgent()
        self.fixer_agent = FixerAgent()
        self.packaging_agent = PackagingAgent()

        self.graph = self._build_graph()

    # ----------------------------------------------------------------------
    # Node wrapper with database logging and error boundary
    # ----------------------------------------------------------------------

    def _wrap_node(self, agent_instance: Any, action_name: str) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
        """Wrap an agent execution in metrics logging and exception capture."""
        def node_fn(state: Dict[str, Any]) -> Dict[str, Any]:
            agent_name = agent_instance.name
            project_name = state.get("project_name", "unnamed_project")
            started_at = datetime.now(timezone.utc).isoformat()
            state["current_agent"] = agent_name

            logger.info(">>> Node started: %s (project=%s)", agent_name, project_name)

            try:
                state = agent_instance.execute(state)
                completed_at = datetime.now(timezone.utc).isoformat()
                
                # Calculate duration
                t0 = datetime.fromisoformat(started_at)
                t1 = datetime.fromisoformat(completed_at)
                duration = round((t1 - t0).total_seconds(), 2)

                summary = ""
                st_info = state.get("agent_status", {}).get(agent_name, {})
                summary = st_info.get("message", f"Completed {action_name}")

                self.db.record_agent_execution(
                    project_name=project_name,
                    agent_name=agent_name,
                    status="completed",
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_seconds=duration,
                    summary=summary,
                )
            except Exception as exc:
                completed_at = datetime.now(timezone.utc).isoformat()
                logger.exception("Node '%s' encountered an unhandled error: %s", agent_name, exc)
                state.setdefault("errors", []).append(f"Node {agent_name} failed: {exc}")
                
                self.db.record_agent_execution(
                    project_name=project_name,
                    agent_name=agent_name,
                    status="failed",
                    started_at=started_at,
                    completed_at=completed_at,
                    error_details=str(exc),
                )
            
            # Persist intermediate project state to SQLite
            self._save_state_to_db(state)
            return state

        return node_fn

    def _save_state_to_db(self, state: Dict[str, Any]) -> None:
        """Helper to sync current state snapshot into SQLite."""
        try:
            self.db.save_project(
                project_name=state.get("project_name", "unnamed_project"),
                description=state.get("project_description", ""),
                status=state.get("agent_status", {}).get(state.get("current_agent", ""), {}).get("status", "running"),
                output_path=state.get("project_output_path", ""),
                specification=state.get("project_specification", {}),
                architecture=state.get("architecture", {}),
                state_dict=state,
            )
        except Exception as exc:
            logger.warning("Could not persist state snapshot to DB: %s", exc)

    # ----------------------------------------------------------------------
    # LangGraph Graph Construction
    # ----------------------------------------------------------------------

    def _build_graph(self) -> Any:
        workflow = StateGraph(dict)

        # 1. Add all agent nodes
        workflow.add_node("requirement_analyst", self._wrap_node(self.requirement_agent, "Requirements Analysis"))
        workflow.add_node("data_discovery", self._wrap_node(self.discovery_agent, "Data Discovery"))
        workflow.add_node("data_architect", self._wrap_node(self.architect_agent, "Data Architecture"))
        workflow.add_node("business_logic", self._wrap_node(self.business_logic_agent, "Business Logic Modeling"))
        workflow.add_node("sql_developer", self._wrap_node(self.sql_agent, "SQL Model Generation"))
        workflow.add_node("yaml_developer", self._wrap_node(self.yaml_agent, "YAML Config Generation"))
        workflow.add_node("data_quality", self._wrap_node(self.data_quality_agent, "Data Quality Testing"))
        workflow.add_node("documentation", self._wrap_node(self.documentation_agent, "Documentation Generation"))
        workflow.add_node("qa_validation", self._wrap_node(self.qa_agent, "Quality Assurance & Validation"))
        workflow.add_node("error_correction", self._wrap_node(self.fixer_agent, "Self-Healing Error Correction"))
        workflow.add_node("project_packaging", self._wrap_node(self.packaging_agent, "Project Packaging"))

        def human_review_node(state: Dict[str, Any]) -> Dict[str, Any]:
            logger.warning("Pipeline entered human_review node: retry limit exceeded or human input required.")
            state["human_approval_required"] = True
            state.setdefault("warnings", []).append("Retry limit reached during error correction. Human review required.")
            return state

        workflow.add_node("human_review", human_review_node)

        # 2. Sequential linear pipeline up to QA
        workflow.add_edge(START, "requirement_analyst")
        workflow.add_edge("requirement_analyst", "data_discovery")
        workflow.add_edge("data_discovery", "data_architect")
        workflow.add_edge("data_architect", "business_logic")
        workflow.add_edge("business_logic", "sql_developer")
        workflow.add_edge("sql_developer", "yaml_developer")
        workflow.add_edge("yaml_developer", "data_quality")
        workflow.add_edge("data_quality", "documentation")
        workflow.add_edge("documentation", "qa_validation")

        # 3. Conditional routing from QA
        def evaluate_qa_result(state: Dict[str, Any]) -> str:
            qa_report = state.get("qa_report", {})
            status = qa_report.get("status", "passed")
            issues = qa_report.get("issues", [])
            error_issues = [i for i in issues if i.get("severity") == "error"]

            retry_count = state.get("retry_count", 0)
            max_retries = state.get("max_retries", 3)

            # Record validation to database
            self.db.record_validation(
                project_name=state.get("project_name", "unnamed_project"),
                validation_type="qa_agent",
                passed=(len(error_issues) == 0 and status == "passed"),
                issues=issues,
            )

            if len(error_issues) == 0:
                logger.info("QA validation passed (no blocking errors)! Proceeding to packaging.")
                return "packaging"

            if retry_count < max_retries:
                state["retry_count"] = retry_count + 1
                logger.info("QA validation found issues. Routing to fixer (attempt %d/%d).", state["retry_count"], max_retries)
                return "fix"
            else:
                logger.warning("Max retries (%d) reached. Escalating to human review.", max_retries)
                return "human_review"

        workflow.add_conditional_edges(
            "qa_validation",
            evaluate_qa_result,
            {
                "packaging": "project_packaging",
                "fix": "error_correction",
                "human_review": "human_review",
            },
        )

        # 4. From error correction, re-run QA validation
        workflow.add_edge("error_correction", "qa_validation")

        # 5. Terminal edges
        workflow.add_edge("project_packaging", END)
        workflow.add_edge("human_review", END)

        return workflow.compile(checkpointer=self.checkpointer)

    # ----------------------------------------------------------------------
    # Execution Interfaces
    # ----------------------------------------------------------------------

    def run(self, initial_state: Dict[str, Any] | ProjectState, thread_id: str = "default_thread") -> Dict[str, Any]:
        """Execute the complete graph synchronously to completion."""
        state_dict = initial_state.model_dump() if isinstance(initial_state, ProjectState) else dict(initial_state)
        config = {"configurable": {"thread_id": thread_id}}
        final_state = self.graph.invoke(state_dict, config=config)

        # Explicitly persist final project status to database
        has_errors = bool(final_state.get("errors", []))
        final_status = "failed" if has_errors else "completed"
        try:
            self.db.save_project(
                project_name=final_state.get("project_name", "unnamed_project"),
                description=final_state.get("project_description", ""),
                status=final_status,
                output_path=final_state.get("project_output_path", ""),
                specification=final_state.get("project_specification", {}),
                architecture=final_state.get("architecture", {}),
                state_dict=final_state,
            )
        except Exception as exc:
            logger.warning("Could not persist final project state to DB: %s", exc)

        return final_state

    def stream(
        self, initial_state: Dict[str, Any] | ProjectState, thread_id: str = "default_thread"
    ) -> Generator[Dict[str, Any], None, None]:
        """Stream graph node updates one by one for real-time frontend feedback."""
        state_dict = initial_state.model_dump() if isinstance(initial_state, ProjectState) else dict(initial_state)
        config = {"configurable": {"thread_id": thread_id}}
        for step_output in self.graph.stream(state_dict, config=config):
            yield step_output


# --------------------------------------------------------------------------
# Top-level functional helpers for frontend and external callers
# --------------------------------------------------------------------------

def create_graph() -> Any:
    """Factory creating and compiling the orchestrator state graph."""
    return Orchestrator().graph


def run_pipeline(initial_state: Dict[str, Any] | ProjectState) -> Dict[str, Any]:
    """Execute the end-to-end multi-agent pipeline."""
    orchestrator = Orchestrator()
    return orchestrator.run(initial_state)

"""AI Agents dashboard page — monitoring and control."""

from __future__ import annotations

import logging
from typing import Any

import streamlit as st

from frontend.components.agent_card import render_agent_grid
from frontend.components.workflow_viz import (
    render_workflow_viz,
    render_progress_bar,
    AGENT_PIPELINE,
)

logger = logging.getLogger(__name__)

try:
    from backend.orchestrator import run_pipeline, create_graph
except ImportError:
    run_pipeline = None
    create_graph = None

try:
    from backend.state import ProjectState
except ImportError:
    ProjectState = None


_AGENT_DESCRIPTIONS: dict[str, str] = {
    "requirement_analyst": "Parses and structures business requirements into a formal specification.",
    "data_discovery": "Discovers source data schemas from Snowflake or uploaded metadata.",
    "data_architect": "Designs the dbt project architecture: layers, models, DAG.",
    "business_logic": "Translates requirements into SQL transformation logic and rules.",
    "sql_developer": "Generates production-ready SQL model files with CTEs and ref().",
    "yaml_developer": "Creates dbt YAML configs: sources, schema, project files.",
    "data_quality": "Designs data quality tests and validation rules.",
    "documentation": "Generates model documentation and descriptions.",
    "qa_validation": "Validates the entire project for correctness and best practices.",
    "error_correction": "Fixes errors found during QA validation.",
    "packaging": "Packages the final dbt project with all files.",
}


def _get_agent_statuses() -> dict[str, Any]:
    """Get current agent statuses from session state."""
    state = st.session_state.get("current_project_state", {})
    return state.get("agent_status", {})


def _build_agent_list(agent_statuses: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a list of agent info dicts for rendering."""
    agents: list[dict[str, Any]] = []
    for agent in AGENT_PIPELINE:
        agent_id = agent["id"]
        status_info = agent_statuses.get(agent_id, {})

        if isinstance(status_info, str):
            status_info = {"status": status_info}

        agents.append({
            "name": agent["name"],
            "description": _AGENT_DESCRIPTIONS.get(agent_id, ""),
            "status": status_info.get("status", "waiting"),
            "start_time": status_info.get("start_time"),
            "end_time": status_info.get("end_time"),
            "output_summary": status_info.get("message", ""),
            "error": status_info.get("error", ""),
        })
    return agents


def render_agents_page() -> None:
    """Render the AI Agents dashboard page."""
    st.markdown("## 🤖 AI Agent Dashboard")
    st.markdown("Monitor and control the multi-agent pipeline execution.")
    st.markdown("---")

    agent_statuses = _get_agent_statuses()
    status_map = {}
    for agent in AGENT_PIPELINE:
        info = agent_statuses.get(agent["id"], {})
        if isinstance(info, str):
            status_map[agent["id"]] = info
        else:
            status_map[agent["id"]] = info.get("status", "waiting")

    # Progress bar
    render_progress_bar(status_map)

    st.markdown("---")

    # Workflow visualization
    render_workflow_viz(status_map)

    st.markdown("---")

    # Controls
    st.markdown("### 🎮 Pipeline Controls")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        start_clicked = st.button(
            "▶️ Start Pipeline",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.get("pipeline_running", False),
        )
    with col2:
        stop_clicked = st.button(
            "⏹️ Stop",
            use_container_width=True,
            disabled=not st.session_state.get("pipeline_running", False),
        )
    with col3:
        if st.button("🔄 Refresh Status", use_container_width=True):
            st.rerun()
    with col4:
        if st.button("🗑️ Clear State", use_container_width=True):
            if "current_project_state" in st.session_state:
                del st.session_state["current_project_state"]
            st.session_state["pipeline_running"] = False
            st.rerun()

    if start_clicked:
        state = st.session_state.get("current_project_state", {})
        if not state.get("business_requirements"):
            st.error("No project configured. Please create a project first in **New Project**.", icon="⚠️")
        elif run_pipeline is not None:
            st.session_state["pipeline_running"] = True
            with st.spinner("🤖 Running agent pipeline..."):
                try:
                    result = run_pipeline(state)
                    st.session_state["current_project_state"] = result
                    st.session_state["pipeline_running"] = False
                    st.success("Pipeline execution complete!", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.session_state["pipeline_running"] = False
                    st.error(f"Pipeline failed: {e}", icon="🚨")
                    logger.exception("Pipeline execution error")
        else:
            st.warning("Backend orchestrator is not available.", icon="⚠️")

    if stop_clicked:
        st.session_state["pipeline_running"] = False
        st.warning("Pipeline stopped.", icon="⏹️")

    st.markdown("---")

    # Agent cards grid
    st.markdown("### 📊 Agent Status")
    agents_list = _build_agent_list(agent_statuses)
    render_agent_grid(agents_list, columns=2)

    # Execution log
    st.markdown("---")
    st.markdown("### 📜 Execution Log")
    state = st.session_state.get("current_project_state", {})
    errors = state.get("errors", [])
    warnings = state.get("warnings", [])

    if errors:
        with st.expander(f"❌ Errors ({len(errors)})", expanded=True):
            for err in errors:
                st.error(str(err))

    if warnings:
        with st.expander(f"⚠️ Warnings ({len(warnings)})", expanded=False):
            for warn in warnings:
                st.warning(str(warn))

    if not errors and not warnings:
        st.info("No execution logs yet.", icon="📜")
